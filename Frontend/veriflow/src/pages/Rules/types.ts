export interface InventoryRule {
  id: string;
  key_id?: string | null;
  rule_name: string;
  matching_claim_key: string;
  expected_value: string;
  is_active: boolean;
  created_at?: string | null;
}

export interface InventoryRuleListResponse {
  items: InventoryRule[];
  limit: number;
  offset: number;
  total: number;
}

export interface CreateInventoryRulePayload {
  rule_name: string;
  matching_claim_key: string;
  expected_value: string;
  key_id?: string | null;
  is_active?: boolean;
}

export interface UpdateInventoryRulePayload {
  rule_name?: string;
  matching_claim_key?: string;
  expected_value?: string;
  key_id?: string | null;
  is_active?: boolean;
}

export interface EvaluateClaimsPayload {
  claims: Record<string, any>;
  key_id?: string | null;
}

export interface RuleViolationItem {
  rule_id: string;
  rule_name: string;
  claim_key: string;
  expected_value: string;
  actual_value: any;
  message: string;
}

export interface EvaluateClaimsResponse {
  status: 'passed' | 'failed';
  total_rules_evaluated: number;
  passed_rules_count: number;
  failed_rules_count: number;
  violations: RuleViolationItem[];
}
