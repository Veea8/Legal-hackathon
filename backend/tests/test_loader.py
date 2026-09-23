from app.loaders.xlsx import DEFAULT_WORKBOOK, load_upload, load_workbook


def test_workbook_loads_five_forms_and_29_fields():
    forms, jury = load_workbook(DEFAULT_WORKBOOK)
    assert [f.form_id for f in forms] == ["F001", "F002", "F003", "F004", "F005"]
    assert sum(len(f.fields) for f in forms) == 29
    assert len(jury) == 29
    assert all(f.stage == "entry" for f in forms)


def test_field_mapping_details():
    forms, _ = load_workbook(DEFAULT_WORKBOOK)
    f001 = forms[0]
    mh = f001.field("mental_health_history")
    assert mh is not None
    assert mh.type == "textarea" and mh.required and mh.sensitive
    assert mh.purpose_text is None  # purpose_stated = N
    assert mh.retention_days == 3650 and mh.destination == "CRM" and mh.third_party_shared

    ins = f001.field("insurance_number")
    assert ins.has_purpose and ins.purpose_text.startswith("Billing")

    cal = forms[1].field("personal_calendar_access")
    assert cal.type == "oauth"


def test_csv_upload_roundtrip():
    csv_text = (
        "form_id,form_name,business_context,field_order,field_name,field_label,field_type,required,"
        "data_category,sensitive_flag,purpose_stated,purpose_text,retention_days,system_destination,third_party_shared\n"
        "U1,Newsletter,Marketing signup,1,email,Email,email,Y,personal,N,Y,Send the newsletter,365,CRM,N\n"
        "U1,Newsletter,Marketing signup,2,birthday,Birthday,date,Y,personal,N,N,,365,CRM,N\n"
    )
    forms = load_upload("x.csv", csv_text.encode())
    assert len(forms) == 1 and forms[0].source == "upload"
    assert [f.field_id for f in forms[0].fields] == ["email", "birthday"]
    assert forms[0].fields[1].purpose_text is None
