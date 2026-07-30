export interface CompositionItem {
  element?: string;
  monomer?: string;
  phase?: string;
  amount?: number;
  unit: string;
  mole_percent?: number;
  weight_fraction?: number;
}

export interface Material {
  id: string;
  name: string;
  material_type: string;
  formula_string?: string;
  hill_formula?: string;
  composition: CompositionItem[];
  aliases: string[];
  description?: string;
  metadata: Record<string, unknown>;
  project_id?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface MaterialCreate {
  name: string;
  material_type: string;
  formula_string?: string;
  hill_formula?: string;
  composition: CompositionItem[];
  aliases: string[];
  description?: string;
  metadata: Record<string, unknown>;
  project_id?: string;
}
