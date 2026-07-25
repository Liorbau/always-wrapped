-- One-time Supabase SQL editor run (also applied on postgres startup by the app).
-- No policies for anon/authenticated => Data API deny; DATABASE_URL still works.

ALTER TABLE public.playlist_timers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.preference_bias ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wrapped_editions ENABLE ROW LEVEL SECURITY;
