import type { Config } from 'tailwindcss';
export default { content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'], theme: { extend: { colors: { noor: { bg:'#05070D', panel:'#0c121e', cyan:'#00E5FF', violet:'#A855F7' } } } }, plugins: [] } satisfies Config;
