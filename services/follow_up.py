"""
Follow-up message generator.
Produces personalised email drafts after a call.
"""


def generate_follow_up(call_output: dict) -> str:
    """
    Generate a follow-up email body based on the structured call output.
    Returns plain-text email body (HTML can be added later).
    """
    lead_type = call_output.get("lead_type", "unknown")
    company = call_output.get("company_name", "")
    contact = call_output.get("contact_name", "")
    country = call_output.get("country", "")
    products = call_output.get("products", [])
    species = call_output.get("species", [])
    volume = call_output.get("volume", "")
    destination = call_output.get("destination_market", "")
    origin = call_output.get("origin_preference", "")
    next_action = call_output.get("next_action", "")
    escalation = call_output.get("human_escalation_required", False)

    name = contact.split()[0] if contact else "there"

    if lead_type == "buyer":
        return _buyer_follow_up(name, company, country, products, species, volume, destination, origin, next_action, escalation)
    elif lead_type == "seller":
        return _seller_follow_up(name, company, country, products, species, destination, next_action, escalation)
    else:
        return _general_follow_up(name, company, next_action, escalation)


def _buyer_follow_up(
    name, company, country, products, species, volume, destination, origin, next_action, escalation
) -> str:
    product_str = ", ".join(products) if products else "timber/wood products"
    species_str = ", ".join(species) if species else "not yet specified"

    lines = [
        f"Hello {name},",
        "",
        f"Thank you for speaking with Fordaq today regarding {company}.",
        "",
        "As discussed, here is a summary of your sourcing requirement:",
        f"  Product:             {product_str}",
        f"  Species:             {species_str}",
    ]
    if volume:
        lines.append(f"  Volume:              {volume}")
    if destination:
        lines.append(f"  Destination market:  {destination}")
    if origin:
        lines.append(f"  Preferred origin:    {origin}")

    lines += [
        "",
        "Recommended next steps:",
        "1. Post or update your buyer request on Fordaq with these details so the",
        "   right suppliers can respond directly.",
        "2. Make sure your company profile and contact details are complete.",
    ]

    if next_action:
        lines += ["", f"Agreed action: {next_action}"]

    if escalation:
        lines += [
            "",
            "A Fordaq sales colleague will contact you shortly to discuss how",
            "Fordaq buyer membership can give you direct access to vetted suppliers.",
        ]

    lines += [
        "",
        "If you have any questions in the meantime, please reply to this email.",
        "",
        "Best regards,",
        "Fordaq Lead Activation Team",
        "www.fordaq.com",
    ]
    return "\n".join(lines)


def _seller_follow_up(
    name, company, country, products, species, markets, next_action, escalation
) -> str:
    product_str = ", ".join(products) if products else "timber/wood products"
    species_str = ", ".join(species) if species else "not yet specified"
    markets_str = markets if markets else "international markets"

    lines = [
        f"Hello {name},",
        "",
        f"Thank you for speaking with Fordaq today regarding {company}.",
        "",
        "Here is a summary of your seller profile based on our conversation:",
        f"  Products:        {product_str}",
        f"  Species:         {species_str}",
        f"  Target markets:  {markets_str}",
        "",
        "Recommended next steps:",
        "1. Complete your Fordaq company profile with full product details.",
        "2. Post clear offers with species, dimensions, grade, volume, origin",
        "   and photos so international buyers can find you.",
        "3. Add your export certifications (FSC, PEFC) if applicable.",
    ]

    if next_action:
        lines += ["", f"Agreed action: {next_action}"]

    if escalation:
        lines += [
            "",
            "A Fordaq sales colleague will contact you to explain how seller",
            "membership gives you direct visibility to buyers in your target markets.",
        ]

    lines += [
        "",
        "If you have any questions, please reply to this email.",
        "",
        "Best regards,",
        "Fordaq Lead Activation Team",
        "www.fordaq.com",
    ]
    return "\n".join(lines)


def _general_follow_up(name, company, next_action, escalation) -> str:
    lines = [
        f"Hello {name},",
        "",
        f"Thank you for speaking with Fordaq today regarding {company}.",
        "",
        "To get the most from your Fordaq listing, we recommend:",
        "1. Complete your company profile with products, markets and contact details.",
        "2. Post your buyer requests or seller offers so the right companies",
        "   can find and contact you directly.",
    ]

    if next_action:
        lines += ["", f"Agreed action: {next_action}"]

    if escalation:
        lines += [
            "",
            "A Fordaq team member will be in touch shortly to provide further support.",
        ]

    lines += [
        "",
        "Best regards,",
        "Fordaq Lead Activation Team",
        "www.fordaq.com",
    ]
    return "\n".join(lines)


def generate_escalation_note(call_output: dict) -> str:
    """
    Generate a short internal escalation note for the sales team.
    """
    lines = [
        "⚡ ESCALATION NOTE — FORDAQ CALLING AGENT",
        f"Company:    {call_output.get('company_name', '')}",
        f"Contact:    {call_output.get('contact_name', '')}",
        f"Country:    {call_output.get('country', '')}",
        f"Phone:      {call_output.get('phone', '')}",
        f"Lead type:  {call_output.get('lead_type', '')}",
        f"Score:      {call_output.get('lead_score', 0)}/100",
        f"Urgency:    {call_output.get('urgency', '')}",
        f"Reason:     {call_output.get('escalation_reason', '')}",
        "",
        f"Summary: {call_output.get('summary', '')}",
        f"Suggested action: {call_output.get('next_action', '')}",
    ]
    return "\n".join(lines)
