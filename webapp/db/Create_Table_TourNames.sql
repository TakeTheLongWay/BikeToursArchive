use tourbook;

-- Auswahlliste der Tournamen für die Combobox auf der Tour-Detailseite.
-- Wird beim Start der App automatisch angelegt (db/database.py: ensure_database)
-- und dabei einmalig mit den vorhandenen Tournamen befüllt.
CREATE TABLE IF NOT EXISTS `tour_names` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tour_names_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
