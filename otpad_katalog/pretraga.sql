-- Pretraga za radnicu. Dvije funkcije, jedno polje za upis.
-- Pokreće se nakon schema.sql. Idempotentno.

-- 1) Upiše broj dijela (u bilo kojem obliku) -> naziv, na koja vozila stane, koliko ih imamo.
CREATE OR REPLACE FUNCTION trazi_broj(q text)
RETURNS TABLE (
    dio_id integer, naziv_hr text, broj text, vrsta text, proizvodjac text,
    marka text, model text, generacija text, godina_od integer, godina_do integer,
    na_zalihi bigint
)
LANGUAGE sql STABLE AS $$
    SELECT d.id, d.naziv_hr, b.broj, b.vrsta, b.proizvodjac,
           v.marka, v.model, v.generacija, v.godina_od, v.godina_do,
           (SELECT count(*) FROM otpad_dio o WHERE o.dio_id = d.id AND o.status = 'NA_ZALIHI')
    FROM dio_broj b
    JOIN dio d              ON d.id = b.dio_id
    LEFT JOIN dio_vozilo dv ON dv.dio_id = d.id
    LEFT JOIN vozilo_tip v  ON v.id = dv.vozilo_tip_id
    WHERE b.broj_norm = norm_broj(q)
    ORDER BY v.marka, v.model, v.godina_od
$$;

-- 2) Upiše vozilo ("focus 2013", "citroen c3") -> tipovi vozila koji odgovaraju.
--    Svaka riječ mora biti u marka+model+generacija; godina (ako je zadana) mora upasti u raspon.
CREATE OR REPLACE FUNCTION trazi_vozilo(q text, godina integer DEFAULT NULL)
RETURNS TABLE (id integer, marka text, model text, generacija text,
               godina_od integer, godina_do integer)
LANGUAGE sql STABLE AS $$
    SELECT v.id, v.marka, v.model, v.generacija, v.godina_od, v.godina_do
    FROM vozilo_tip v
    WHERE NOT EXISTS (
        SELECT 1
        FROM unnest(string_to_array(trim(bez_dijakritika(q)), ' ')) AS w
        WHERE w <> ''
          AND bez_dijakritika(v.marka || ' ' || v.model || ' ' || v.generacija)
              NOT LIKE '%' || w || '%'
    )
      AND (godina IS NULL
           OR (godina BETWEEN v.godina_od AND coalesce(v.godina_do, 9999)))
    -- točan naziv modela (npr. "Focus") ide prije srodnih ("Focus kombi", "Focus C-Max")
    ORDER BY (bez_dijakritika(v.model) = ANY (string_to_array(trim(bez_dijakritika(q)), ' '))) DESC,
             v.marka, v.model, v.godina_od
$$;
