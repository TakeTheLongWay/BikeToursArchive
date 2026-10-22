use tourbook;

-- Bereits importierte BikeTracker-Dateien (Google-Drive-ID bzw. Dateiname bei
-- lokaler Quelle) mit der zugehörigen Tour. Die BikeTracker-Seite zeigt damit
-- in der Spalte "Importiert" an, welche Dateien schon übernommen wurden.
-- Wird beim Start der App automatisch angelegt (db/database.py: ensure_database).
CREATE TABLE IF NOT EXISTS `biketracker_imports` (
  `file_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `activity_id` bigint NOT NULL,
  `imported_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`file_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
