use tourbook;

-- Sammlungen: Ordnungsbegriff für eine zusammengefasste Menge an Touren.
-- image = optional hochgeladenes Bild der Sammlung (max. 10 MB), image_mimetype dessen Typ.
-- Wird beim Start der App automatisch angelegt (db/database.py: ensure_database).
CREATE TABLE IF NOT EXISTS `collections` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image` mediumblob,
  `image_mimetype` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_collections_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
