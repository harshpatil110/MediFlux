# MediFlux Plain-English Business Policies

This document specifies the core dynamic business rules for the MediFlux pharmaceutical supply chain.
The Bootstrap Coding Agent compiles these policies into verified, versioned Python modules.

---

## 1. Margin Rules (`margin_rules`)
- **Category**: Wholesale & Retail Margin Enforcement
- **Contract**: `def run(input: dict) -> dict`
- **Rules**:
  - Minimum acceptable wholesale margin is **15%** (`0.15`).
  - Transactions with a margin below **10%** (`0.10`) must be flagged as critical margin breach.
- **Input Specification**:
  - `cost_price`: Base acquisition cost in INR (float)
  - `selling_price`: Proposed selling price in INR (float)
- **Output Specification**:
  - `margin_percentage`: Calculated margin ratio `(selling_price - cost_price) / selling_price` (float)
  - `margin_inr`: Net margin in INR (float)
  - `meets_minimum`: Boolean, true if `margin_percentage >= 0.15`
  - `flagged`: Boolean, true if `margin_percentage < 0.10`

---

## 2. Volume Discount (`volume_discount`)
- **Category**: Tiered Bulk Order Pricing
- **Contract**: `def run(input: dict) -> dict`
- **Rules**:
  - Orders above **100 strips**: Apply **2%** (`0.02`) discount.
  - Orders above **500 strips**: Apply **5%** (`0.05`) discount.
  - Orders above **1000 strips**: Apply **8%** (`0.08`) discount.
  - Orders of 100 strips or fewer receive 0% discount.
- **Input Specification**:
  - `quantity`: Number of strips ordered (int)
  - `unit_price`: Base price per strip in INR (float)
- **Output Specification**:
  - `discount_percentage`: Applied discount rate (float)
  - `discount_amount`: Total discount deducted in INR (float)
  - `final_total`: Payable amount after discount (float)

---

## 3. Credit Check Rules (`credit_check_rules`)
- **Category**: Node Financial Exposure & Solvency Guard
- **Contract**: `def run(input: dict) -> dict`
- **Rules**:
  - Calculate total exposure as `outstanding_balance + order_total`.
  - Standard credit ceiling is **50,000 INR** unless a specific `credit_limit` is provided.
  - If total exposure exceeds `credit_limit`, the order must be **blocked** (`approved = False`).
- **Input Specification**:
  - `outstanding_balance`: Current unpaid ledger balance in INR (float)
  - `order_total`: Total value of new incoming order in INR (float)
  - `credit_limit`: Maximum allowed exposure in INR (optional float, defaults to 50000.0)
- **Output Specification**:
  - `approved`: Boolean, true if `total_exposure <= credit_limit`
  - `total_exposure`: Combined existing balance and order total (float)
  - `credit_limit`: Applied credit limit (float)
  - `breached_by`: Excess amount over limit if blocked, otherwise 0.0 (float)

---

## 4. Price Ceiling Rules (`price_ceiling`)
- **Category**: National Essential Medicines List (NEML) Price Cap Compliance
- **Contract**: `def run(input: dict) -> dict`
- **Rules**:
  - Proposed unit price must not exceed statutory `neml_ceiling_price`.
  - Non-compliant pricing must be rejected and excess amount documented.
- **Input Specification**:
  - `medicine_id`: Master SKU identifier (string)
  - `unit_price`: Proposed pricing per unit in INR (float)
  - `neml_ceiling_price`: Maximum allowable price per unit in INR (float)
- **Output Specification**:
  - `compliant`: Boolean, true if `unit_price <= neml_ceiling_price`
  - `unit_price`: Submitted price (float)
  - `ceiling_price`: Statutory ceiling (float)
  - `excess_amount`: Overcharge amount `max(0.0, unit_price - neml_ceiling_price)` (float)

