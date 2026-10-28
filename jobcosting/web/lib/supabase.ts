import { createClient } from "@supabase/supabase-js";

// Nur der öffentliche anon-Key gehört ins Frontend; Zugriff schützen JWT + RLS.
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
