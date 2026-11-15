-- Migration: Add unique barcode to public.products for Pharmacy POS Lite
ALTER TABLE public.products ADD COLUMN IF NOT EXISTS barcode VARCHAR(64) UNIQUE;
CREATE INDEX IF NOT EXISTS idx_products_barcode ON public.products(barcode);
