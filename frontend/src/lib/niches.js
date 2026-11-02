// The tag vocabulary, mirrored from backend/niche_tagging.py — a drift test
// fails if the two disagree. Adding a tag is one line here and one line there.
//
// Never free text: every value a creator, an admin, a brand or the model may
// set is a key below, and the server drops anything else.

export const NICHES_BY_CATEGORY = {
    "fnb": {
        "fine_dining": "Fine dining",
        "casual_dining": "Casual dining",
        "cafes_coffee": "Cafés & coffee",
        "bakery_desserts": "Bakery & desserts",
        "street_food": "Street food",
        "south_indian": "South Indian",
        "north_indian": "North Indian",
        "coastal_regional": "Coastal & regional",
        "asian": "Asian",
        "continental": "Continental",
        "bars_cocktails": "Bars & cocktails",
        "craft_beer": "Craft beer",
        "vegan_vegetarian": "Vegan & vegetarian",
        "healthy_eating": "Healthy eating",
        "home_cooking": "Home cooking"
    },
    "hospitality": {
        "luxury_stays": "Luxury stays",
        "boutique_hotels": "Boutique hotels",
        "staycations": "Staycations",
        "events_weddings": "Events & weddings"
    },
    "retail": {
        "home_decor": "Home décor",
        "gadgets": "Gadgets",
        "books_stationery": "Books & stationery",
        "local_markets": "Local markets"
    },
    "real_estate": {
        "apartments": "Apartments",
        "villas_plots": "Villas & plots",
        "interiors": "Interiors"
    },
    "fashion": {
        "streetwear": "Streetwear",
        "ethnic_wear": "Ethnic wear",
        "jewellery_accessories": "Jewellery & accessories",
        "sustainable_fashion": "Sustainable fashion"
    },
    "travel": {
        "weekend_getaways": "Weekend getaways",
        "adventure": "Adventure",
        "heritage_culture": "Heritage & culture",
        "road_trips": "Road trips"
    },
    "wellness": {
        "fitness": "Fitness",
        "yoga_meditation": "Yoga & meditation",
        "skincare_beauty": "Skincare & beauty",
        "salons_spa": "Salons & spa"
    },
    "lifestyle": {
        "parenting_family": "Parenting & family",
        "pets": "Pets",
        "nightlife": "Nightlife",
        "art_design": "Art & design",
        "tech_gaming": "Tech & gaming"
    }
};

export const LANGUAGES = {
    "kannada": "Kannada",
    "english": "English",
    "hindi": "Hindi",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "malayalam": "Malayalam"
};

export const TONES = {
    "reviews": "Reviews",
    "humour": "Humour",
    "aesthetic": "Aesthetic",
    "vlog": "Vlog",
    "educational": "Educational"
};

export const AREAS = {
    "indiranagar": "Indiranagar",
    "koramangala": "Koramangala",
    "jayanagar": "Jayanagar",
    "jp_nagar": "JP Nagar",
    "hsr_layout": "HSR Layout",
    "whitefield": "Whitefield",
    "malleshwaram": "Malleshwaram",
    "mg_road": "MG Road",
    "brigade_road": "Brigade Road",
    "church_street": "Church Street",
    "ub_city": "UB City",
    "lavelle_road": "Lavelle Road",
    "residency_road": "Residency Road",
    "richmond_town": "Richmond Town",
    "frazer_town": "Frazer Town",
    "cox_town": "Cox Town",
    "ulsoor": "Ulsoor",
    "domlur": "Domlur",
    "btm_layout": "BTM Layout",
    "banashankari": "Banashankari",
    "basavanagudi": "Basavanagudi",
    "rajajinagar": "Rajajinagar",
    "sadashivanagar": "Sadashivanagar",
    "rt_nagar": "RT Nagar",
    "hebbal": "Hebbal",
    "yelahanka": "Yelahanka",
    "sahakar_nagar": "Sahakar Nagar",
    "marathahalli": "Marathahalli",
    "bellandur": "Bellandur",
    "sarjapur_road": "Sarjapur Road",
    "electronic_city": "Electronic City",
    "kalyan_nagar": "Kalyan Nagar",
    "hennur": "Hennur",
    "kammanahalli": "Kammanahalli",
    "banaswadi": "Banaswadi",
    "cv_raman_nagar": "CV Raman Nagar",
    "old_airport_road": "Old Airport Road",
    "vasanth_nagar": "Vasanth Nagar",
    "cunningham_road": "Cunningham Road",
    "bannerghatta_road": "Bannerghatta Road",
    "yeshwanthpur": "Yeshwanthpur"
};

export const FORMATS = {
    "reel": "Reels",
    "carousel": "Carousels",
    "image": "Photos"
};

export const NICHE_LABELS = Object.fromEntries(
    Object.values(NICHES_BY_CATEGORY).flatMap((group) => Object.entries(group)),
);

const TABLES = { niche: NICHE_LABELS, languages: LANGUAGES, tone: TONES, shoots_in: AREAS, areas: AREAS, formats: FORMATS };

/** The words for a tag: `labelOf("niche", "craft_beer")` → "Craft beer". */
export function labelOf(kind, key) {
    return (TABLES[kind] || {})[key] || key;
}

/** The tag kinds a person edits, in the order the editor shows them. */
export const TAG_KINDS = [
    { key: "niche", label: "What you post about" },
    { key: "languages", label: "Languages" },
    { key: "tone", label: "Style" },
    { key: "shoots_in", label: "Where you shoot" },
];

/** Options for one kind, as `[key, label]` pairs. */
export function optionsFor(kind) {
    return Object.entries(kind === "niche" ? NICHE_LABELS : TABLES[kind] || {});
}
