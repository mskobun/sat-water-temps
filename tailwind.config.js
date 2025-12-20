/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			colors: {
				'deep-navy': '#0b1a2e',
				'dark-blue': '#102a43',
				'mid-blue': '#1f4f96',
				'accent-blue': '#00aaff',
				'cyan': '#48c6ef',
				'dark-bg': '#121212',
				'dark-surface': '#1e1e1e',
				'dark-card': '#222',
				'amber': '#f9a44a',
			},
			fontFamily: {
				'poppins': ['Poppins', 'sans-serif'],
			},
			animation: {
				'fade-in': 'fadeIn 0.5s ease-out forwards',
				'spin-slow': 'spin 2s linear infinite',
			},
			keyframes: {
				fadeIn: {
					'0%': { opacity: '0', transform: 'scale(0.9)' },
					'100%': { opacity: '1', transform: 'scale(1)' },
				},
			},
		},
	},
	plugins: [],
};

