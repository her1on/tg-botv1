import { SUPABASE_URL, SUPABASE_ANON_KEY } from './env.js';

const isConfigured =
  SUPABASE_URL &&
  !SUPABASE_URL.startsWith('your-') &&
  SUPABASE_ANON_KEY &&
  !SUPABASE_ANON_KEY.startsWith('your-');

/**
 * Initialized Supabase client, or null if credentials are not configured.
 * In demo mode (null), form submissions are simulated locally.
 * @type {import('@supabase/supabase-js').SupabaseClient|null}
 */
export const supabase =
  isConfigured && window.supabase
    ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
    : null;
