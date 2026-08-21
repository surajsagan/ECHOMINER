# echo_extractor.py
import fitz  # PyMuPDF
import re
import pandas as pd

def _clean_text_line(s):
    if not s:
        return ""
    # remove weird unicode artefacts and trim
    s = s.replace('\x0c', ' ')
    s = s.replace('Ã¢â‚¬Â¢', ' ')
    return re.sub(r'\s+', ' ', s).strip()

def extract_echo_data(pdf_path):
    """
    Input: path to a PDF containing one or more echo reports.
    Output: pandas DataFrame where each row is one parsed report and columns are your variables.
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()

    # Split by a report separator used in your files
    records = re.split(r"Echo Technologist", full_text)

    # Patterns (based on your original script), made a bit more flexible (allow decimals)
    patterns = {
        "Name": re.compile(r"Name\s+(.+?)\s+Age\s*/\s*Gender", re.IGNORECASE | re.DOTALL),
        "Age / Gender": re.compile(r"Age\s*/\s*Gender\s*[:\s]*([\d]{1,3})\s*/\s*([MFmf])", re.IGNORECASE),
        "Address": re.compile(r"Address\s+([^\n\r]+)", re.IGNORECASE),
        "AO": re.compile(r"AO\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "LA": re.compile(r"LA\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "RV": re.compile(r"RV\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "L VID d": re.compile(r"L VID d\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "L VID s": re.compile(r"L VID s\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "IVS d": re.compile(r"IVS d\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "IVS s": re.compile(r"IVS s\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "LVPW d": re.compile(r"LVPW d\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "LVPW s": re.compile(r"LVPW s\s+(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE),
        "EDV": re.compile(r"\bEDV\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*ml", re.IGNORECASE),
        "ESV": re.compile(r"\bESV\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*ml", re.IGNORECASE),
        "SV": re.compile(r"\bSV\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*ml", re.IGNORECASE),
        "EF": re.compile(r"EF\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),
        "FS": re.compile(r"FS\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),
        "FINDINGS": re.compile(r"FINDINGS\s*[:\-]?\s*(.*?)\bIMPRESSION\b", re.DOTALL | re.IGNORECASE)
    }

    finding_fields = [
        "Left Ventricle", "Left Atrium", "Right Ventricle", "Right Atrium", "Aorta",
        "Pulmonary Artery", "IVS", "IAS", "Mitral Valve", "Aortic Valve", "Tricuspid Valve",
        "Pulmonary Valve", "Pericardium", "Colour Doppler", "Doppler Study", "Others"
    ]

    impression_fields = [f"IMPRESSION{i}" for i in range(1, 11)]

    base_columns = [
        "Name", "Age / Gender", "Address", "AO", "LA", "RV",
        "L VID d", "L VID s", "IVS d", "IVS s", "LVPW d", "LVPW s",
        "EDV", "ESV", "SV", "EF", "FS", "MV", "TV", "AV", "PV"
    ]

    all_columns = base_columns + finding_fields + impression_fields

    structured_records = []

    for entry in records:
        entry = entry.strip()
        if not entry:
            continue

        row = {col: "" for col in all_columns}

        # Apply basic patterns
        for key, pattern in patterns.items():
            match = pattern.search(entry)
            if match:
                if key == "Age / Gender":
                    row[key] = f"{match.group(1)} / {match.group(2).upper()}"
                elif key == "FINDINGS":
                    findings_text = match.group(1)
                    for field in finding_fields:
                        parts = field.split()
                        flexible_field = r"\s+".join(parts)
                        pattern_line = rf"{flexible_field}\s*[:\-]?\s*(.*)"
                        fmatch = re.search(pattern_line, findings_text, re.IGNORECASE)
                        if fmatch:
                            value = fmatch.group(1).strip(" :\t\r\n")
                            row[field] = _clean_text_line(value)
                else:
                    row[key] = _clean_text_line(match.group(1))

        # Doppler block (same logic you used)
        doppler_block = re.search(r"Doppler Study(.*?)FINDINGS", entry, re.DOTALL | re.IGNORECASE)
        if doppler_block:
            doppler_text = doppler_block.group(1)
            e_values = re.findall(r"\bE\s*(\d+(?:\.\d+)?)\b", doppler_text)
            a_values = re.findall(r"\bA\s*(\d+(?:\.\d+)?)\b", doppler_text)
            vmax_pattern = re.findall(r"V[-]?\s*max\s*[:\-]?\s*(\d+(?:\.\d+)?)", doppler_text, re.IGNORECASE)
            if len(e_values) >= 2 and len(a_values) >= 2:
                row["MV"] = f"E{e_values[0]}, A{a_values[0]}"
                row["TV"] = f"E{e_values[1]}, A{a_values[1]}"
            if len(vmax_pattern) >= 2:
                row["AV"] = f"Vmax {vmax_pattern[0]}"
                row["PV"] = f"Vmax {vmax_pattern[1]}"

        # Name fallback
        if not row["Name"]:
            name_fallback = re.search(r"Name\s+(.+?)\s+Age\s*/\s*Gender", entry, re.IGNORECASE | re.DOTALL)
            if name_fallback:
                row["Name"] = _clean_text_line(name_fallback.group(1))

        # IMPRESSION block (flexible)
        imp_match = re.search(r"IMPRESSION\s*[:\-]?\s*(.*)", entry, re.IGNORECASE | re.DOTALL)
        if imp_match:
            impression_block = imp_match.group(1).strip()
            # split lines, remove bullets and garbage
            bullets = []
            for line in impression_block.splitlines():
                cleaned = _clean_text_line(line)
                cleaned = re.sub(r'^[\u2022\-\*\. ]+', '', cleaned)  # remove bullets like • - *
                if cleaned:
                    bullets.append(cleaned)
            for i, bullet in enumerate(bullets[:10]):
                row[f"IMPRESSION{i+1}"] = bullet

        structured_records.append(row)

    return pd.DataFrame(structured_records)
