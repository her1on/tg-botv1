-- Supabase migration script
-- Run in Supabase SQL Editor

-- ─── Indexes for bookings ────────────────────────────────────────────────────

-- Speeds up get_user_bookings (called on every "my bookings" tap)
CREATE INDEX IF NOT EXISTS idx_bookings_user_date
    ON bookings (user_id, date);

-- Speeds up get_booked_times and cleanup_old_bookings
CREATE INDEX IF NOT EXISTS idx_bookings_date
    ON bookings (date);

-- ─── Indexes for appointments ────────────────────────────────────────────────

-- Speeds up get_booked_times UNION side and get_unnotified_web_bookings
CREATE INDEX IF NOT EXISTS idx_appointments_date
    ON appointments (appointment_date);

CREATE INDEX IF NOT EXISTS idx_appointments_notified
    ON appointments (owner_notified, appointment_date)
    WHERE owner_notified = false;

-- ─── RLS policies for appointments ──────────────────────────────────────────

-- Allow anonymous inserts from the website frontend
CREATE POLICY IF NOT EXISTS "anon can insert appointments"
    ON appointments
    FOR INSERT
    TO anon
    WITH CHECK (source = 'web');

-- Prevent anon from reading or modifying existing rows
-- (service role used by the bot bypasses RLS)

-- ─── NOTIFY trigger for instant owner alerts ─────────────────────────────────

-- Fires pg_notify('new_appointment', row_json) on every INSERT into appointments.
-- The bot's pg_listener.py listens on this channel and notifies the owner
-- in real-time instead of waiting for the 10-minute fallback poll.
CREATE OR REPLACE FUNCTION notify_new_appointment()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('new_appointment', row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER appointments_insert_notify
    AFTER INSERT ON appointments
    FOR EACH ROW EXECUTE FUNCTION notify_new_appointment();
