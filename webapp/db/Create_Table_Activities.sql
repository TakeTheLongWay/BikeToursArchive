use bikedesk;

CREATE TABLE `activities` (
  `activity_id` bigint NOT NULL AUTO_INCREMENT,
  `activity_date` datetime NOT NULL,
  `activity_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `activity_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `elapsed_time_s` int DEFAULT NULL,
  `distance_km` decimal(10,3) DEFAULT NULL,
  `gear_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `filename` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `elevation_gain_m` decimal(6,1) DEFAULT NULL,
  `min_elevation_m` decimal(6,1) DEFAULT NULL,
  `max_elevation_m` decimal(6,1) DEFAULT NULL,
  `avg_watts` int DEFAULT NULL,
  `calories` int DEFAULT NULL,
  `is_commute` tinyint(1) DEFAULT NULL,
  `bike_id` bigint DEFAULT NULL,
  `media` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`activity_id`)
) ENGINE=InnoDB AUTO_INCREMENT=16710935280 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

