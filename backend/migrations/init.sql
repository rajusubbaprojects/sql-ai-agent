-- backend/migrations/init.sql
-- Creates the airlines table and seeds it for CI

CREATE TABLE IF NOT EXISTS airlines (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    airline             VARCHAR(100),
    flight_number       INT,
    airport_from        CHAR(3),
    airport_to          CHAR(3),
    day_of_week         INT,
    flight_time_integer INT,
    flight_length       INT,
    delay               INT,
    flight_time         TIME
);

INSERT INTO airlines
    (airline, flight_number, airport_from, airport_to,
     day_of_week, flight_time_integer, flight_length, delay, flight_time)
VALUES
    ('Delta Air Lines',    100, 'ATL', 'LAX', 1, 900,  245, 10, '15:00:00'),
    ('United Airlines',    200, 'ORD', 'SFO', 2, 1000, 260, 0,  '09:30:00'),
    ('Southwest Airlines', 300, 'DAL', 'PHX', 3, 600,  130, 5,  '11:15:00'),
    ('American Airlines',  400, 'DFW', 'JFK', 4, 1100, 195, 20, '07:45:00'),
    ('JetBlue Airways',    500, 'BOS', 'MCO', 5, 950,  180, 0,  '13:00:00'),
    ('Alaska Airlines',    600, 'SEA', 'SAN', 6, 850,  155, 8,  '16:30:00');
