"""
BORG FENIX — Narodne Novine Feed Scraper + LLM Semantic Extractor

Hibridni pipeline:
1. Feed Watchdog: RSS parse, duplikat check po URL-u
2. Sanitizer: HTML → čisti Markdown (BeautifulSoup + html2text)
3. Semantic Extractor: Claude Haiku parsira zakon → strukturirani JSON

Pokreće se svakih 6h via Celery beat.

HARDENED v2 (2026-03-23):
- Strict Proxy Mode: bez HR_PROXY_URL scraper NE radi (štiti server IP)
- Dead-proxy alerting: WhatsApp ALERT ako proxy ne odgovara
- SSL verify=True po defaultu (verify=False samo ako PROXY_SKIP_SSL=1)
"""
import json
import logging
import os
from datetime import datetime

import feedparser
import html2text
import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from limit_connect_ai.models_knowledge_graph import RegulatorySource, RegulatoryUpdate

logger = logging.getLogger(__name__)


class ProxyUnavailableError(Exception):
    """HR proxy ne odgovara — scraper se gasi."""
    pass


class NNFeedScraperService:
    """Scraper za Narodne novine RSS + LLM ekstrakcija."""

    # Fallback RSS URL-ovi ako baza nema endpoint
    NN_RSS_URLS = [
        'https://narodne-novine.nn.hr/rss.aspx',
        'https://narodne-novine.nn.hr/rss/',
    ]

    # Timeout za proxy health check i HTTP zahtjeve
    PROXY_TIMEOUT = 15
    HTTP_TIMEOUT = 20

    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = True
        self.html_converter.ignore_images = True
        self.html_converter.ignore_tables = False
        self.html_converter.body_width = 0  # Bez word-wrapa

        self._proxy_url = os.environ.get('HR_PROXY_URL', '').strip()
        self._skip_ssl = os.environ.get('PROXY_SKIP_SSL', '0') == '1'

    @property
    def proxies(self):
        if not self._proxy_url:
            return None
        return {'http': self._proxy_url, 'https': self._proxy_url}

    def _check_proxy_health(self):
        """Provjeri da li HR proxy odgovara. Baca ProxyUnavailableError ako ne."""
        if not self._proxy_url:
            raise ProxyUnavailableError(
                'HR_PROXY_URL nije postavljen u .env — scraper neće raditi bez proxyja '
                'kako bi zaštitio IP reputaciju produkcijskog servera.'
            )

        try:
            resp = requests.get(
                'https://narodne-novine.nn.hr/',
                proxies=self.proxies,
                timeout=self.PROXY_TIMEOUT,
                verify=not self._skip_ssl,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
            )
            if resp.status_code >= 500:
                raise ProxyUnavailableError(
                    f'HR proxy vratio status {resp.status_code} za NN health check'
                )
        except requests.exceptions.ProxyError as e:
            raise ProxyUnavailableError(f'HR proxy connection error: {e}')
        except requests.exceptions.ConnectTimeout as e:
            raise ProxyUnavailableError(f'HR proxy timeout: {e}')
        except requests.exceptions.ConnectionError as e:
            raise ProxyUnavailableError(f'HR proxy connection refused: {e}')
        except ProxyUnavailableError:
            raise
        except Exception as e:
            raise ProxyUnavailableError(f'HR proxy unexpected error: {e}')

    def _send_proxy_alert(self, error_msg):
        """Pošalji WhatsApp ALERT da je FENIX oslijepio."""
        try:
            from core.notify import notify
            notify(
                'ALERT',
                f'FENIX Intelligence je oslijepio!\n\n'
                f'HR Proxy ne odgovara — scraper zaustavljen.\n'
                f'Greška: {str(error_msg)[:200]}\n\n'
                f'Scraper neće dohvaćati NN podatke dok se proxy ne popravi.\n'
                f'Server IP reputacija je zaštićena.',
                urgent=True,
            )
        except Exception as e:
            logger.error('[NN] Neuspjeli WhatsApp alert: %s', e)

    def _proxied_get(self, url):
        """HTTP GET kroz HR proxy. Nikada ne koristi direktnu vezu."""
        return requests.get(
            url,
            timeout=self.HTTP_TIMEOUT,
            proxies=self.proxies,
            verify=not self._skip_ssl,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/123.0.0.0 Safari/537.36',
                'Accept-Language': 'hr-HR,hr;q=0.9,en;q=0.8',
            },
        )

    def process_feed(self):
        """Glavni entry point — dohvati RSS, parsiraj, LLM ekstrakcija."""
        # ── Proxy health check (fail-fast) ────────────────────
        try:
            self._check_proxy_health()
        except ProxyUnavailableError as e:
            logger.error('[NN] PROXY DOWN: %s', e)
            self._send_proxy_alert(e)
            return {'processed': 0, 'skipped': 0, 'errors': 1, 'proxy_error': str(e)}

        logger.info('[NN] Proxy health OK — pokrećem scrape')

        source = self._get_source()
        if not source:
            logger.error('[NN] RegulatorySource za Narodne novine ne postoji')
            return {'processed': 0, 'skipped': 0, 'errors': 0}

        feed_url = source.url_endpoint or self.NN_RSS_URLS[0]
        logger.info('[NN] Dohvaćam feed: %s', feed_url)

        try:
            resp = self._proxied_get(feed_url)
            feed = feedparser.parse(resp.content)
        except requests.exceptions.ProxyError as e:
            logger.error('[NN] Proxy pao tijekom feed downloada: %s', e)
            self._send_proxy_alert(f'Proxy pao tijekom RSS downloada: {e}')
            return {'processed': 0, 'skipped': 0, 'errors': 1, 'proxy_error': str(e)}
        except Exception as e:
            logger.error('[NN] Feed parse error: %s', e)
            return {'processed': 0, 'skipped': 0, 'errors': 1}

        if not feed.entries:
            logger.info('[NN] Feed prazan ili nedostupan (bozo_exception=%s)',
                        getattr(feed, 'bozo_exception', 'none'))
            # Update last_scraped čak i ako je prazan
            source.last_scraped = timezone.now()
            source.save(update_fields=['last_scraped'])
            return {'processed': 0, 'skipped': 0, 'errors': 0}

        processed = 0
        skipped = 0
        errors = 0

        for entry in feed.entries:
            link = getattr(entry, 'link', '')
            title = getattr(entry, 'title', '')

            if not link:
                continue

            # Duplikat check po URL-u
            if RegulatoryUpdate.objects.filter(url=link).exists():
                skipped += 1
                continue

            # Preuzimanje HTML-a kroz HR proxy
            try:
                resp = self._proxied_get(link)
                resp.raise_for_status()
            except requests.exceptions.ProxyError as e:
                logger.error('[NN] Proxy pao za %s: %s — zaustavljam batch', link, e)
                self._send_proxy_alert(f'Proxy pao tijekom article scrape: {e}')
                errors += 1
                break  # Prekini cijeli batch — proxy je mrtav
            except requests.exceptions.RequestException as e:
                logger.warning('[NN] HTTP error za %s: %s', link, e)
                errors += 1
                continue

            # Sanitize HTML → Markdown
            clean_markdown = self._sanitize_html(resp.text)
            if len(clean_markdown.strip()) < 100:
                logger.debug('[NN] Preskačem %s — premalo sadržaja', link)
                skipped += 1
                continue

            # LLM ekstrakcija
            llm_result = self._extract_semantics_via_llm(clean_markdown, title)
            if not llm_result:
                # Fallback: spremi s osnovnim podacima
                llm_result = {
                    'title': title,
                    'category': 'OTHER',
                    'effective_date': None,
                    'impact_score': 3,
                    'is_opportunity': False,
                    'impact_keywords': [],
                }

            # Spremi u bazu
            try:
                self._create_regulatory_update(source, entry, link, llm_result, clean_markdown)
                processed += 1
            except Exception as e:
                logger.error('[NN] DB save error za %s: %s', link, e)
                errors += 1

        # Update last_scraped
        source.last_scraped = timezone.now()
        source.save(update_fields=['last_scraped'])

        logger.info('[NN] Feed završen: processed=%d, skipped=%d, errors=%d',
                    processed, skipped, errors)
        return {'processed': processed, 'skipped': skipped, 'errors': errors}

    def _get_source(self):
        """Dohvati ili kreiraj RegulatorySource za NN."""
        try:
            return RegulatorySource.objects.get(source_type='nn')
        except RegulatorySource.DoesNotExist:
            return None

    def _sanitize_html(self, html_content):
        """HTML → čisti Markdown. Uklanja navigaciju, header, footer, JS, CSS."""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Ukloni vizualni šum
        for el in soup(['header', 'footer', 'nav', 'script', 'style', 'aside',
                        'iframe', 'form', 'button', 'input']):
            el.decompose()

        # Pronađi glavni sadržaj — NN koristi razne ID-jeve
        main = (
            soup.find('div', id='dokument')
            or soup.find('div', class_='doc-body')
            or soup.find('article')
            or soup.find('div', class_='content')
            or soup.find('main')
            or soup.find('body')
        )

        if not main:
            return ''

        markdown = self.html_converter.handle(str(main))
        # Skrati na ~15K znakova da ne probijemo token limit
        return markdown[:15000]

    def _extract_semantics_via_llm(self, markdown_text, fallback_title=''):
        """Pošalji tekst Claudeu za semantičku ekstrakciju."""
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            logger.warning('[NN] ANTHROPIC_API_KEY nije postavljen — preskačem LLM')
            return None

        system_prompt = (
            "Ti si pravni i porezni asistent specijaliziran za hrvatsko zakonodavstvo. "
            "Tvoj zadatak je pročitati tekst zakona/pravilnika i vratiti ISKLJUČIVO validan JSON, "
            "bez ikakvog dodatnog teksta, bez markdown blokova.\n\n"
            "Očekivani JSON format:\n"
            "{\n"
            '  "title": "Službeni naslov akta",\n'
            '  "category": "TAX" | "VAT" | "LABOUR" | "FISCAL" | "ERACUN" | "CORP" | '
            '"TRADE" | "GDPR" | "AML" | "NONPROFIT" | "EU_FUND" | "OTHER",\n'
            '  "effective_date": "YYYY-MM-DD" ili null,\n'
            '  "impact_score": 1-10,\n'
            '  "is_opportunity": true/false,\n'
            '  "impact_keywords": ["ključna_riječ_1", "ključna_riječ_2"],\n'
            '  "affected_modules": ["pos", "invoicing", "payroll", "eracun", "konto"]\n'
            "}\n\n"
            "Pravila:\n"
            "- impact_score 8-10: direktno utječe na poreze, plaće ili fiskalizaciju\n"
            "- impact_score 5-7: utječe na poslovanje ali nije hitan\n"
            "- impact_score 1-4: informativno, nema direktnog utjecaja\n"
            "- is_opportunity=true: zakon donosi olakšice, poticaje, izuzeća\n"
            "- affected_modules: koji LIMIT Connect moduli su pogođeni\n"
        )

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)

            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=1000,
                temperature=0.1,
                system=system_prompt,
                messages=[{
                    'role': 'user',
                    'content': f'Analiziraj ovaj tekst i vrati JSON:\n\n{markdown_text[:12000]}',
                }],
            )

            text = response.content[0].text.strip()

            # Čišćenje markdown code blocks ako ih ima
            if text.startswith('```'):
                text = text.split('\n', 1)[1] if '\n' in text else text[3:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)
            logger.info('[NN] LLM ekstrakcija OK: %s (score=%s)',
                        result.get('title', '?')[:50], result.get('impact_score'))
            return result

        except json.JSONDecodeError as e:
            logger.warning('[NN] LLM vratio neispravan JSON: %s', str(e)[:100])
            return None
        except Exception as e:
            logger.error('[NN] LLM ekstrakcija error: %s', e)
            return None

    def _create_regulatory_update(self, source, entry, link, llm_result, markdown_text):
        """Kreiraj RegulatoryUpdate iz LLM rezultata."""
        eff_date = None
        eff_date_str = llm_result.get('effective_date')
        if eff_date_str:
            try:
                eff_date = datetime.strptime(eff_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass

        # Ako je opportunity, podigni impact
        impact = llm_result.get('impact_score', 3)
        if llm_result.get('is_opportunity'):
            impact = max(impact, 8)

        # NN broj iz naslova (npr. "NN 123/2026")
        nn_number = ''
        title = llm_result.get('title', getattr(entry, 'title', ''))
        if 'NN' in title.upper():
            import re
            nn_match = re.search(r'NN\s*(\d+/\d{4})', title, re.IGNORECASE)
            if nn_match:
                nn_number = f'NN {nn_match.group(1)}'

        # Publication date iz RSS entry
        pub_date = timezone.now().date()
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                pub_date = datetime(*entry.published_parsed[:3]).date()
            except Exception:
                pass

        keywords = llm_result.get('impact_keywords', [])
        affected = llm_result.get('affected_modules', [])

        update = RegulatoryUpdate.objects.create(
            source=source,
            title=title[:500],
            category=llm_result.get('category', 'OTHER'),
            nn_number=nn_number,
            publication_date=pub_date,
            effective_date=eff_date,
            raw_text=markdown_text[:5000],
            ai_summary=f"Ključne riječi: {', '.join(keywords)}. "
                       f"Prilika: {'Da' if llm_result.get('is_opportunity') else 'Ne'}.",
            impact_score=impact,
            affected_modules=affected,
            is_processed=True,
            is_breaking=impact >= 9,
            url=link,
        )

        logger.info('[NN] Kreiran RegulatoryUpdate: %s (impact=%d, cat=%s)',
                    update.title[:60], impact, update.category)

        return update
