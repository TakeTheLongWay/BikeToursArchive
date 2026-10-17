use tourbook;

-- Setzt bei jeder neuen Tour ohne Bike das Standard-Bike aus der Einstellung
-- bikes.standard_bike (Bike-Name oder Bike-ID). Greift unabhängig davon, wie
-- die Tour in die Datenbank kommt (Import-Button, BikeTracker, tools/, SQL).
-- Wird beim Start der App automatisch angelegt (db/database.py: ensure_database).
DELIMITER //

CREATE TRIGGER `trg_activities_default_bike`
BEFORE INSERT ON `activities`
FOR EACH ROW
BEGIN
  IF NEW.bike_id IS NULL OR NEW.bike_id = 0 THEN
    SET NEW.bike_id = (
      SELECT b.id
      FROM bikes b
      JOIN appsettings s ON s.setting_key = 'bikes.standard_bike'
      WHERE b.name = TRIM(s.setting_value)
         OR CAST(b.id AS CHAR) COLLATE utf8mb4_unicode_ci = TRIM(s.setting_value)
      ORDER BY b.name = TRIM(s.setting_value) DESC
      LIMIT 1
    );
  END IF;
END //

DELIMITER ;
