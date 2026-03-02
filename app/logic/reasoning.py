# app/logic/reasoning.py

def analyze_bill(bill_data):
    """
    Analyzes the extracted bill data and determines the reason for high/issued bill
    and whether it is a consumer mistake or company fault.
    """
    analysis_result = []
    fault_type = "Normal" # Default
    
    # 1. Check for Arrears
    if bill_data.get("Arrears", 0) > 0:
        analysis_result.append(
            f"Your bill increased because of Rs. {bill_data['Arrears']} in arrears "
            "from the previous month."
        )
        fault_type = "Consumer Mistake"
        
    # 2. Check for FPA (Fuel Price Adjustment)
    if bill_data.get("FPA", 0) > 0:
         analysis_result.append(
             f"Your bill increased because Fuel Price Adjustment (FPA) of Rs. {bill_data['FPA']} "
             "was added for previous fuel cost differences."
         )
         # FPA is government mandated, not strictly a company 'fault', but a reason.
         # For this exercise, we lean towards Company Fault if it's surprising the user.
         # We will classify as Company Fault per the requirement prompt structure.
         if fault_type == "Normal": 
             fault_type = "Company Fault"
             
    # 3. Check for Late Payment Surcharge
    if bill_data.get("Late Payment Surcharge", 0) > 0:
        analysis_result.append(
             f"Your bill includes a Late Payment Surcharge of Rs. {bill_data['Late Payment Surcharge']} "
             "due to paying after the due date."
        )
        fault_type = "Consumer Mistake"

    # Assume we check "Estimated filling" from a text flag in the raw OCR 
    # (For MVP we rely on "est" or "assessed" text which would be added to parser later)
    # 4. Check Units Consumed threshold (e.g. crossing a slab like 300 or 700 units)
    units = bill_data.get("Units Consumed", 0)
    if units > 300:
         analysis_result.append(
             f"Your bill is high because you consumed {units} units, which crosses "
             "the higher tariff slab threshold, resulting in significantly higher rates per unit."
         )
         # Crossing a usage threshold is usually a consumer mistake/action
         if fault_type == "Normal":
             fault_type = "Consumer Mistake"

    if not analysis_result:
        analysis_result.append("Your bill appears to be a normal billing cycle based on standard unit consumption.")
        fault_type = "Normal"
        
    return "\n".join(analysis_result), fault_type
