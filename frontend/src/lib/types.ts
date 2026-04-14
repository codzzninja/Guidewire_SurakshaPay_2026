export type User = {
  id: number;
  phone: string;
  full_name: string;
  platform: string;
  zone_id: string;
  upi_id: string;
  avg_hours_per_day: number;
  lat: number;
  lon: number;
  /** Device GPS trace samples stored (MSTS / anti-spoofing) */
  gps_sample_count?: number;
  gps_captured_at?: string | null;
};

export type Policy = {
  id: number;
  plan_type: string;
  weekly_premium: number;
  max_weekly_coverage: number;
  max_per_event: number;
  status: string;
  payment_status: string;
  payment_provider: string;
  premium_payment_id: string;
  premium_paid_amount: number;
  premium_paid_at?: string | null;
  week_start: string;
  week_end: string;
};

export type PremiumQuote = {
  plan_type: string;
  base_weekly_premium: number;
  /** XGBoost output before zone safety credit */
  ml_risk_adjustment: number;
  /** Negative INR: rubric-style discount in historically safer zones */
  zone_safety_premium_credit: number;
  /** ml_risk_adjustment + zone_safety_premium_credit */
  risk_adjustment: number;
  final_weekly_premium: number;
  max_weekly_coverage: number;
  max_per_event: number;
  feature_snapshot: Record<string, unknown>;
  pricing_explainability: Record<string, unknown>;
  dynamic_coverage: Record<string, unknown>;
};

export type Claim = {
  id: number;
  event_id: string;
  disruption_type: string;
  income_loss: number;
  payout_amount: number;
  premium_paid_amount: number;
  premium_payment_id: string;
  status: string;
  fraud_score: number;
  fraud_notes: string;
  payout_ref: string;
  created_at: string;
};
