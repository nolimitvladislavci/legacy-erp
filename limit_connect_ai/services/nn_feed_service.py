"""
BORG FENIX — Narodne Novine Scraper + LLM Semantic Extractor

Pipeline:
1. Web scraper: POST na NN tražilicu → lista zakona po godini/mjesecu
2. Article fetch: dohvati HTML svakog zakona
3. Sanitizer: HTML → čisti Markdown
4. LLM ekstrakcija: Claude Haiku → strukturirani JSON

Pokreće se svakih 6h via Celery beat.

ADAPTIVE v3 (2026-03-24):
- Bez RSS (NN nema javni RSS feed) — koristi web scraping NN tražilice
- Bez obveznog proxyja — direktna veza s rate limitingom (2s između zahtjeva)
- Proxy opcionalan: ako HR_PROXY_URL postoji, koristi ga za article fetch
- Scraping samo zakona (eli/sluzbeni), ne oglasnog dijela
"""

import json
import logging
import os
import time
from datetime import datetime

import html2text
import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from limit_connect_ai.models_knowledge_graph import RegulatorySource, RegulatoryUpdate

logger = logging.getLogger(__name__)

NN_BASE = "https://narodne-novine.nn.hr"
NN_SEARCH_URL = f"{NN_BASE}/search.aspx"
ARTICLE_DELAY = 2  # sekunde između zahtjeva — courtesy prema NN serveru
HTTP_TIMEOUT = 20

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


class NNFeedScraperService:
    """Scraper za Narodne novine + LLM semantic ekstrakcija."""

    def __init__(self):
        self._proxy_url = os.environ.get("HR_PROXY_URL", "").strip()
        self._skip_ssl = os.environ.get("PROXY_SKIP_SSL", "0") == "1"
        self._session = requests.Session()
        self._session.headers["User-Agent"] = BROWSER_UA

        self.html_conv = html2text.HTML2Text()
        self.html_conv.ignore_links = True
        self.html_conv.ignore_images = True
        self.html_conv.body_width = 0

    # ── HTTP helpers ────────────────────────────────────────────

    @property
    def _proxies(self):
        return {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None

    def _get(self, url):
        return self._session.get(url, timeout=HTTP_TIMEOUT, proxies=self._proxies, verify=not self._skip_ssl)

    def _post(self, url, data):
        return self._session.post(
            url, data=data, timeout=HTTP_TIMEOUT, proxies=self._proxies, verify=not self._skip_ssl
        )

    # ── NN tražilica ────────────────────────────────────────────

    def _get_viewstate(self):
        """Dohvati ASP.NET VIEWSTATE s NN tražilice."""
        r = self._get(NN_SEARCH_URL)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return {
            "__VIEWSTATE": (soup.find("input", {"name": "__VIEWSTATE"}) or {}).get("value", ""),
            "__VIEWSTATEGENERATOR": (soup.find("input", {"name": "__VIEWSTATEGENERATOR"}) or {}).get("value", ""),
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
        }

    def _fetch_nn_issue_list(self, year: int, month: int) -> list[dict]:
        """
        Dohvati listu zakona za zadani mjesec/godinu.
        Strategija:
          1. POST na NN tražilicu → lista brojeva glasnika za taj mjesec
          2. Za svaki broj glasnika: dohvati HTML stranicu → lista pojedinačnih zakona
        Vraća: [{'url': str, 'title': str, 'nn_number': str}, ...]
        """
        # Korak 1: lista glasnika za mjesec
        try:
            state = self._get_viewstate()
        except Exception as e:
            logger.error("[NN] Viewstate fetch error: %s", e)
            return []

        payload = {
            **state,
            "btnPopisSvihIzadnja": "Prikaži",
            "ddlGodina": str(year),
            "ddlMjesec": str(month),
            "ddlResultPerPage": "100",
        }

        try:
            r = self._post(NN_SEARCH_URL, payload)
            r.raise_for_status()
        except Exception as e:
            logger.error("[NN] Search POST error: %s", e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")

        # Nađi linkove na glasnike (eli/sluzbeni/YYYY/N) — bez /pdf
        issue_urls = []
        seen_issues = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if f"/eli/sluzbeni/{year}/" not in href:
                continue
            # Uzmi samo broj glasnika (eli/sluzbeni/2026/25), preskoči PDF
            parts = href.rstrip("/").split("/")
            try:
                idx = parts.index("sluzbeni")
                issue_num = parts[idx + 2].split("?")[0].split("/")[0]
                if not issue_num.isdigit():
                    continue
                issue_url = f"{NN_BASE}/eli/sluzbeni/{year}/{issue_num}"
                if issue_url not in seen_issues:
                    seen_issues.add(issue_url)
                    issue_urls.append((issue_url, int(issue_num)))
            except (ValueError, IndexError):
                continue

        logger.info("[NN] %d/%02d: %d glasnika pronađeno", year, month, len(issue_urls))

        # Korak 2: za svaki glasnik dohvati listu zakona (HTML)
        results = []
        seen_articles = set()

        for issue_url, issue_num in sorted(issue_urls, key=lambda x: x[1]):
            time.sleep(1)  # ljubaznost prema NN serveru
            try:
                r = self._get(issue_url)
                r.raise_for_status()
            except Exception as e:
                logger.warning("[NN] Glasnik fetch error %s: %s", issue_url, e)
                continue

            s2 = BeautifulSoup(r.text, "html.parser")
            nn_num = f"NN {issue_num}/{year}"

            for a in s2.find_all("a", href=True):
                href = a.get("href", "")
                title = a.text.strip()

                if "/clanci/sluzbeni/" not in href:
                    continue
                if not title or len(title) < 5:
                    continue

                art_url = href if href.startswith("http") else NN_BASE + href
                if art_url in seen_articles:
                    continue
                seen_articles.add(art_url)

                results.append(
                    {
                        "url": art_url,
                        "title": title,
                        "nn_number": nn_num,
                    }
                )

            logger.debug("[NN] Glasnik %s: %d zakona", nn_num, len([x for x in results if x["nn_number"] == nn_num]))

        logger.info("[NN] %d/%02d: %d zakona ukupno", year, month, len(results))
        return results

    # ── Article scraping ────────────────────────────────────────

    def _fetch_article_markdown(self, url: str) -> str:
        """Dohvati i sanitiziraj jedan zakon → Markdown."""
        time.sleep(ARTICLE_DELAY)
        try:
            r = self._get(url)
            r.raise_for_status()
        except Exception as e:
            logger.warning("[NN] Article fetch error %s: %s", url, e)
            return ""

        soup = BeautifulSoup(r.text, "html.parser")
        for el in soup(["header", "footer", "nav", "script", "style", "aside", "iframe", "form", "button", "input"]):
            el.decompose()

        main = (
            soup.find("div", id="dokument")
            or soup.find("div", class_="doc-body")
            or soup.find("article")
            or soup.find("div", class_="content")
            or soup.find("main")
            or soup.find("body")
        )
        if not main:
            return ""

        return self.html_conv.handle(str(main))[:15000]

    # ── LLM ekstrakcija ─────────────────────────────────────────

    def _extract_via_llm(self, markdown: str, fallback_title: str = "") -> dict | None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None

        system = (
            "Ti si pravni asistent za hrvatsko zakonodavstvo. "
            "Vrati SAMO validan JSON, bez markdown blokova:\n"
            '{"title":"...","category":"TAX|VAT|LABOUR|FISCAL|ERACUN|CORP|TRADE|GDPR|AML|NONPROFIT|EU_FUND|OTHER",'
            '"effective_date":"YYYY-MM-DD ili null","impact_score":1-10,'
            '"is_opportunity":true/false,"impact_keywords":["kw1"],'
            '"affected_modules":["pos","invoicing","payroll","eracun","konto"]}\n'
            "impact_score 8-10 = direktno utječe na poreze/plaće/fiskalizaciju. "
            "is_opportunity=true = donosi olakšice ili poticaje."
        )

        try:
            from anthropic import Anthropic

            resp = Anthropic(api_key=api_key).messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                temperature=0.1,
                system=system,
                messages=[{"role": "user", "content": f"Analiziraj:\n\n{markdown[:10000]}"}],
            )
            text = resp.content[0].text.strip().strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("[NN] LLM neispravan JSON: %s", e)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("[NN] LLM error: %s", e)
        return None

    # ── Glavni entry point ──────────────────────────────────────

    def process_feed(self):
        """Dohvati zakone za tekući i prethodni mjesec, parsiraj, spremi."""
        now = timezone.now()
        year = now.year
        month = now.month

        source = self._get_or_create_source()

        # Dohvati ovaj i prethodni mjesec (za sigurnost)
        months_to_check = [(year, month)]
        if month == 1:
            months_to_check.append((year - 1, 12))
        else:
            months_to_check.append((year, month - 1))

        all_items = []
        for y, m in months_to_check:
            all_items.extend(self._fetch_nn_issue_list(y, m))

        # Dedupliciraj
        seen_urls = set(
            RegulatoryUpdate.objects.filter(url__in=[i["url"] for i in all_items]).values_list("url", flat=True)
        )

        new_items = [i for i in all_items if i["url"] not in seen_urls]
        logger.info("[NN] %d novih zakona za obradu", len(new_items))

        processed = skipped = errors = 0
        skipped = len(all_items) - len(new_items)

        for item in new_items:
            markdown = self._fetch_article_markdown(item["url"])
            if len(markdown.strip()) < 100:
                skipped += 1
                continue

            llm = self._extract_via_llm(markdown, item["title"])
            if not llm:
                llm = {
                    "title": item["title"],
                    "category": "OTHER",
                    "effective_date": None,
                    "impact_score": 3,
                    "is_opportunity": False,
                    "impact_keywords": [],
                    "affected_modules": [],
                }

            try:
                self._save_update(source, item, llm, markdown)
                processed += 1
            except Exception as e:
                logger.error("[NN] DB save error %s: %s", item["url"], e)
                errors += 1

        source.last_scraped = timezone.now()
        source.save(update_fields=["last_scraped"])

        logger.info("[NN] Završeno: processed=%d skipped=%d errors=%d", processed, skipped, errors)
        return {"processed": processed, "skipped": skipped, "errors": errors}

    # ── Helpers ─────────────────────────────────────────────────

    def _get_or_create_source(self):
        src, _ = RegulatorySource.objects.get_or_create(
            source_type="nn",
            defaults={
                "name": "Narodne novine",
                "url_endpoint": NN_SEARCH_URL,
                "is_active": True,
            },
        )
        return src

    def _save_update(self, source, item: dict, llm: dict, markdown: str):
        eff_date = None
        if llm.get("effective_date"):
            try:
                eff_date = datetime.strptime(llm["effective_date"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        impact = int(llm.get("impact_score", 3))
        if llm.get("is_opportunity"):
            impact = max(impact, 8)

        keywords = llm.get("impact_keywords", [])
        affected = llm.get("affected_modules", [])

        RegulatoryUpdate.objects.create(
            source=source,
            title=llm.get("title", item["title"])[:500],
            category=llm.get("category", "OTHER"),
            nn_number=item.get("nn_number", ""),
            publication_date=timezone.now().date(),
            effective_date=eff_date,
            raw_text=markdown[:5000],
            ai_summary=(
                f"Ključne riječi: {', '.join(keywords)}. Prilika: {'Da' if llm.get('is_opportunity') else 'Ne'}."
            ),
            impact_score=impact,
            affected_modules=affected,
            is_processed=True,
            is_breaking=impact >= 9,
            url=item["url"],
        )
        logger.info("[NN] Spremljeno: %s (impact=%d)", item["title"][:60], impact)
