/**
 * Fixed category → chart-slot colors — single source of truth for every
 * screen (mirrors the --mm-cat-* tokens in styles.scss). The "gallery"
 * tuning of the heritage family: same eight hues as the validated set,
 * lifted chroma/luminance for real presence on the dark surface.
 * Color follows the category forever, never its rank in a chart.
 */
export const CATEGORY_COLORS: { [key: string]: string } = {
  RENT_AND_UTILITIES: '#6c9de6',        // cornflower
  TRANSFER_IN: '#6c9de6',
  TRAVEL: '#27b9de',                    // petrol
  INCOME: '#27b9de',
  TRANSPORTATION: '#dba43e',            // ochre
  GOVERNMENT_AND_NON_PROFIT: '#dba43e',
  MEDICAL: '#a9bf49',                   // olive
  HOME_IMPROVEMENT: '#a9bf49',
  ENTERTAINMENT: '#b189e0',             // mauve
  TRANSFER_OUT: '#b189e0',
  LOAN_PAYMENTS: '#8f93ea',             // indigo
  BANK_FEES: '#8f93ea',
  GENERAL_MERCHANDISE: '#e07b9f',       // rose
  PERSONAL_CARE: '#e07b9f',
  FOOD_AND_DRINK: '#e27c4e',            // terracotta
  GENERAL_SERVICES: '#e27c4e'
};

export const OTHER_COLOR = '#86817a';

/** Envelope band slots — same family, fixed order per envelope. */
export const SLOT_COLORS = [
  '#6c9de6',
  '#27b9de',
  '#dba43e',
  '#a9bf49',
  '#b189e0',
  '#8f93ea',
  '#e07b9f',
  '#e27c4e'
];

export function categoryColor(category: string | null | undefined): string {
  return CATEGORY_COLORS[(category || '').toUpperCase()] || OTHER_COLOR;
}
