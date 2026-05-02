module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint', 'react-refresh'],
  rules: {
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    'no-restricted-globals': ['error', 'alert', 'confirm', 'prompt'],
    // TypeScript handles undefined-variable and redeclaration checking
    'no-undef': 'off',
    'no-redeclare': 'off',
    // Allow unused vars in TS (tsc catches these as errors anyway)
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': 'off',
  },
}
