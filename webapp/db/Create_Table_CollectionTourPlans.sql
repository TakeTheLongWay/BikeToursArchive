use tourbook;

-- Zuordnung geplanter Tracks (tour_plans) zu Sammlungen (collections).
-- Ein Track kann in mehreren Sammlungen liegen; wird eine Sammlung oder Planung gelöscht,
-- entfällt die Zuordnung automatisch.
-- Wird beim Start der App automatisch angelegt (db/database.py: ensure_database).
CREATE TABLE IF NOT EXISTS `collection_tour_plans` (
  `collection_id` int NOT NULL,
  `tour_plan_id` int NOT NULL,
  `added_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`collection_id`, `tour_plan_id`),
  KEY `idx_collection_tour_plans_plan` (`tour_plan_id`),
  CONSTRAINT `fk_collection_tour_plans_collection` FOREIGN KEY (`collection_id`)
    REFERENCES `collections` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_collection_tour_plans_plan` FOREIGN KEY (`tour_plan_id`)
    REFERENCES `tour_plans` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
