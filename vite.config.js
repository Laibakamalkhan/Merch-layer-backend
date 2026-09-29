import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Port fix rakha hai taake Supabase redirect URL hamesha match kare.
  server: { port: 5173, strictPort: true },
})
