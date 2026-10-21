from invoice_reader.evaluate import same


def test_text_fields_ignore_case_but_not_ligatures():
    assert same("vendor_name", "Brightline Office Supply", "BRIGHTLINE OFFICE SUPPLY ")
    # "Oﬃce" with the one-character ligature looks right but fails a spreadsheet search, so it counts as wrong.
    assert not same("vendor_name", "Brightline Office Supply", "Brightline Oﬃce Supply")
