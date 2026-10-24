-- ==============================================================================
-- TABLA: orden_medica (Supabase PostgreSQL)
-- Emisión oficial de solicitudes de análisis de laboratorio y ecografía SOP
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.orden_medica (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES public.paciente(id) ON DELETE CASCADE,
    consulta_id UUID REFERENCES public.consulta(id) ON DELETE SET NULL,
    medico_id UUID REFERENCES public.medico(id) ON DELETE SET NULL,
    fecha_emision TIMESTAMPTZ DEFAULT NOW(),
    tipo_ecografia VARCHAR(50) DEFAULT 'transvaginal',
    indicacion_ecografia TEXT,
    examenes_laboratorio JSONB DEFAULT '[]'::jsonb,
    indicaciones_preanaliticas TEXT,
    diagnostico_presuntivo TEXT DEFAULT 'Sospecha de Síndrome de Ovario Poliquístico (CIE-10: E28.2) — Protocolo Rotterdam',
    estado VARCHAR(30) DEFAULT 'vigente',
    prioridad VARCHAR(20) DEFAULT 'normal',
    observaciones TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Políticas de seguridad RLS
ALTER TABLE public.orden_medica ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'orden_medica' AND policyname = 'Permitir acceso completo a ordenes medicas'
    ) THEN
        CREATE POLICY "Permitir acceso completo a ordenes medicas" ON public.orden_medica FOR ALL USING (true);
    END IF;
END $$;
