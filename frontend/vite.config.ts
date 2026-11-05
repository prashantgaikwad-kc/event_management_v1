import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [
    vue(),
    frappeui({
      frappeProxy: true,
      lucideIcons: true,
      frontendRoute: '/event-portal',
    }),
  ],
})