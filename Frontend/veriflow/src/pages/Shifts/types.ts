export interface ShiftRecord {
  id: string;
  user_id: number;
  key_id: string;
  device_id?: string | null;
  status: 'active' | 'ended' | 'revoked' | 'expired' | string;
  started_at?: string | null;
  expires_at?: string | null;
  ended_at?: string | null;
  revoked_reason?: string | null;
}

export interface ShiftListResponse {
  items: ShiftRecord[];
  limit: number;
  offset: number;
  total: number;
}

export interface StartShiftPayload {
  target_user_id?: number | null;
  key_id?: string | null;
  duration_hours: number;
  device_id?: string | null;
  include_rules?: boolean;
}

export interface StartShiftResponse {
  shift: ShiftRecord;
  shift_token: string;
  expires_at: string;
  qr_code_base64?: string | null;
}

export interface ReissueShiftResponse {
  shift: ShiftRecord;
  shift_token: string;
  expires_at: string;
  qr_code_base64?: string | null;
}
