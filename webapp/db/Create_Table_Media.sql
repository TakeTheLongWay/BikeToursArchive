use tourbook;

-- Bilder und Videos aus dem Strava-Export (legacy_data/media.csv) mit Bildunterschrift.
-- filename = "Medien-Dateiname" ohne den Pfadanteil "media/", die Dateien liegen im
-- BikeTracker-Unterordner images; caption = "Medienunterschrift" (leer -> NULL).
-- Wird beim Start der App automatisch angelegt (db/database.py: ensure_database),
-- befüllt mit tools/import_media.py.
CREATE TABLE IF NOT EXISTS `media` (
  `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `caption` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`filename`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
