import { api } from './client';

export type BudgetSuggestion = {
  month: string;
  suggested_total: number;
  breakdown: {
    needs: number;
    wants: number;
    savings: number;
  };
  tips?: string[];
  analytics: {
    month_over_month_change_pct: number;
    current_month_expenses: number;
    previous_month_expenses: number;
    top_categories: Array<{ category_id: string; amount: number }>;
  };
  persona?: string;
  method: 'gemini' | 'heuristic' | string;
  warnings?: string[];
  net_flow?: number;
};

export type WeeklySummary = {
  period_start: string;
  period_end: string;
  current_week_total: number;
  previous_week_total: number;
  week_over_week_change_pct: number;
  top_categories: Array<{ category_id: string; amount: number }>;
  anomalies: Array<{
    category_id: string;
    current_amount: number;
    previous_amount: number;
    change_pct: number;
  }>;
  daily_breakdown: Record<string, number>;
  tips: string[];
};

export async function getBudgetSuggestion(params?: {
  month?: string;
  geminiApiKey?: string;
  persona?: string;
}): Promise<BudgetSuggestion> {
  const monthQuery = params?.month ? `?month=${encodeURIComponent(params.month)}` : '';
  const headers: Record<string, string> = {};
  if (params?.geminiApiKey) headers['X-Gemini-Api-Key'] = params.geminiApiKey;
  if (params?.persona) headers['X-Insight-Persona'] = params.persona;
  return api<BudgetSuggestion>(`/insights/budget-suggestion${monthQuery}`, { headers });
}

export async function getWeeklySummary(params?: {
  endDate?: string;
}): Promise<WeeklySummary> {
  const query = params?.endDate ? `?end_date=${encodeURIComponent(params.endDate)}` : '';
  return api<WeeklySummary>(`/insights/weekly-summary${query}`);
}
