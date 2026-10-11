# =============================================================================
# SNOMED Cluster Manager - ECL lessons for the Playground
# =============================================================================
# Each lesson teaches one ECL idea with an example analysts meet in practice.
# Counts were checked against the terminology server on 11 October 2026 and
# change with each SNOMED CT release.

STATIN = "372912004 |Substance with 3-hydroxy-3-methylglutaryl-coenzyme A reductase inhibitor mechanism of action|"
STATIN_PRODUCTS = (
    "<< 373873005 |Pharmaceutical / biologic product| :\n"
    f"    127489000 |Has active ingredient| = << {STATIN}"
)
DOAC_INGREDIENTS = (
    "(<< 698090000 |Apixaban| OR << 442031002 |Rivaroxaban|\n"
    "     OR << 712778008 |Edoxaban| OR << 700029008 |Dabigatran|)"
)

LESSON_STAGES = [
    {
        "stage": "1. Basics",
        "lessons": [
            {
                "title": "Start with one concept",
                "why": (
                    "Every SNOMED CT concept has a numeric ID. The text between `|` pipes "
                    "is a label for readers; the server ignores it."
                ),
                "ecl": "73211009 |Diabetes mellitus|",
                "notice": (
                    "1 code: the concept itself. A record coded as *Type 2 diabetes mellitus* "
                    "would not match, which is why clusters rarely use a bare concept."
                ),
            },
            {
                "title": "Include everything below it with <<",
                "why": (
                    "SNOMED CT is a hierarchy. `<<` returns the concept and every more specific "
                    "concept beneath it, so codes added in future releases are picked up "
                    "automatically."
                ),
                "ecl": "<< 73211009 |Diabetes mellitus|",
                "notice": (
                    "About 124 codes, from type 1 and type 2 to diabetes with complications. "
                    "`<` returns the same set without the parent concept (123)."
                ),
                "compare": {
                    "label": "Try < (below only)",
                    "ecl": "< 73211009 |Diabetes mellitus|",
                },
            },
            {
                "title": "Remove what you don't want with MINUS",
                "why": (
                    "When a hierarchy includes concepts your definition shouldn't, `MINUS` "
                    "removes them; with `<<` it removes everything below that concept too."
                ),
                "ecl": (
                    "<< 73211009 |Diabetes mellitus|\n"
                    "MINUS << 11687002 |Gestational diabetes mellitus|"
                ),
                "notice": (
                    "117 codes: the gestational diabetes branch is gone. Read the remaining list "
                    "for anything else your definition should exclude."
                ),
            },
            {
                "title": "Combine branches with OR",
                "why": (
                    "When a definition spans sibling concepts without a useful common parent, "
                    "list each branch and join them with `OR`."
                ),
                "ecl": (
                    "<< 433144002 |Chronic kidney disease stage 3|\n"
                    "OR << 431857002 |Chronic kidney disease stage 4|\n"
                    "OR << 433146000 |Chronic kidney disease stage 5|"
                ),
                "notice": (
                    "About 75 codes. The list includes *Anaemia in chronic kidney disease stage 5*, "
                    "because SNOMED places it under stage 5. Hierarchies bring in co-occurring and "
                    "'due to' concepts, so always read the results."
                ),
            },
        ],
    },
    {
        "stage": "2. Find by meaning",
        "lessons": [
            {
                "title": "Find by body site",
                "why": (
                    "A refinement (`: attribute = value`) filters on how a concept is defined, not "
                    "what it is called. Here: every malignant disease whose finding site is in "
                    "the lung."
                ),
                "ecl": (
                    "<< 363346000 |Malignant neoplastic disease| :\n"
                    "    363698007 |Finding site| = << 39607008 |Lung structure|"
                ),
                "notice": (
                    "About 266 codes, covering histological types such as acinar cell carcinoma "
                    "that a text search for 'lung cancer' would miss."
                ),
            },
            {
                "title": "Find by cause",
                "why": (
                    "The causative agent attribute finds every infection caused by an organism, "
                    "however the condition is named."
                ),
                "ecl": (
                    "<< 40733004 |Infectious disease| :\n"
                    "    246075003 |Causative agent| = << 3092008 |Staphylococcus aureus|"
                ),
                "notice": (
                    "About 50 codes, including impetigo and sycosis barbae, whose names don't "
                    "mention the organism, and the MRSA and MSSA pneumonias."
                ),
            },
            {
                "title": "Keep attributes together with { }",
                "why": (
                    "Without braces, each attribute can match a different part of a concept's "
                    "definition. Braces require both attributes in the same relationship group, "
                    "so the virus must be the cause of the lung finding."
                ),
                "ecl": (
                    "<< 40733004 |Infectious disease| : {\n"
                    "    246075003 |Causative agent| = << 49872002 |Virus|,\n"
                    "    363698007 |Finding site| = << 39607008 |Lung structure| }"
                ),
                "notice": (
                    "37 codes grouped, against 45 without braces. The extra 8 are infections where "
                    "a virus and a lung site appear in separate parts of the definition."
                ),
                "compare": {
                    "label": "Try without braces",
                    "ecl": (
                        "<< 40733004 |Infectious disease| :\n"
                        "    246075003 |Causative agent| = << 49872002 |Virus|,\n"
                        "    363698007 |Finding site| = << 39607008 |Lung structure|"
                    ),
                },
            },
        ],
    },
    {
        "stage": "3. Medicines",
        "lessons": [
            {
                "title": "Medicines by ingredient: wrap in an outer <<",
                "why": (
                    "Products are found through their ingredients. The UK dm+d products recorded "
                    "in GP systems sit below the international product concepts and do not carry "
                    "the ingredient attribute themselves, so wrap the expression in `<< ( ... )`."
                ),
                "ecl": (
                    "<< (\n"
                    "  << 373873005 |Pharmaceutical / biologic product| :\n"
                    f"    127489000 |Has active ingredient| = {DOAC_INGREDIENTS}\n"
                    ")"
                ),
                "notice": (
                    "About 304 codes, including UK products and packs such as *Apixaban 1mg/ml oral "
                    "suspension*. Without the outer `<<` you get 13 international concepts and "
                    "would miss almost every prescription."
                ),
                "compare": {
                    "label": "Try without the outer <<",
                    "ecl": (
                        "<< 373873005 |Pharmaceutical / biologic product| :\n"
                        f"    127489000 |Has active ingredient| = {DOAC_INGREDIENTS}"
                    ),
                },
            },
            {
                "title": "Medicines by drug class",
                "why": (
                    "Many substances are grouped by mechanism of action, so one expression finds "
                    "every statin, including any added later."
                ),
                "ecl": f"<< (\n  {STATIN_PRODUCTS}\n)",
                "notice": (
                    "About 1,000 codes. Combination products such as amlodipine with atorvastatin "
                    "are included; decide whether your definition wants them. Save medicine "
                    "clusters with the MEDICATION type."
                ),
            },
            {
                "title": "See what's inside a set with .",
                "why": (
                    "A dot returns the attribute values instead of the concepts: here, every "
                    "ingredient in a statin-containing product. It is a quick way to explore a set "
                    "before saving it."
                ),
                "ecl": f"(\n  {STATIN_PRODUCTS}\n) . 127489000 |Has active ingredient|",
                "notice": (
                    "18 substances: the statins plus combination partners such as amlodipine and "
                    "aspirin. Use them to spot combination products to exclude."
                ),
            },
        ],
    },
    {
        "stage": "4. Lists and records",
        "lessons": [
            {
                "title": "Use a reference set with ^",
                "why": (
                    "Reference sets are lists maintained by NHS England or SNOMED International. "
                    "`^` returns their members."
                ),
                "ecl": "^ 999002381000000108 |Safeguarding issues simple reference set|",
                "notice": (
                    "55 codes. Before writing ECL for a QOF condition, check the brought-in "
                    "codesets in this app: the national PCD clusters, such as AST_COD for asthma, "
                    "are already there and kept current."
                ),
            },
            {
                "title": "Include retired codes with history supplements",
                "why": (
                    "Older records hold concepts that have since been retired. History supplements "
                    "add inactive concepts linked to your active ones."
                ),
                "ecl": "<< 44054006 |Type 2 diabetes mellitus| {{ +HISTORY-MIN }}",
                "notice": (
                    "14 active codes become 32 with `+HISTORY-MIN` and 38 with `+HISTORY-MAX`. "
                    "MIN adds concepts with the same meaning; MAX also adds looser matches, so "
                    "check them."
                ),
                "compare": {
                    "label": "Try +HISTORY-MAX",
                    "ecl": "<< 44054006 |Type 2 diabetes mellitus| {{ +HISTORY-MAX }}",
                },
            },
            {
                "title": "Search by words to explore",
                "why": (
                    "A term filter matches description text. Use it to find where concepts sit in "
                    "the hierarchy, not as the final definition."
                ),
                "ecl": '<< 404684003 |Clinical finding| {{ term = "frailty" }}',
                "notice": (
                    "15 codes. Use the results to find the right parent concept, then build the "
                    "cluster with `<<` and refinements: word matches miss synonyms and pick up "
                    "unrelated concepts."
                ),
            },
        ],
    },
]
