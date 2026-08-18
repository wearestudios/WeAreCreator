/**
 * What creators make, and where they are.
 *
 * Mirrors CREATOR_TAXONOMY and INDIAN_CITIES in backend/server.py, and a unit
 * test fails if the two drift apart. Duplicated rather than fetched because
 * these are the first things on screen in the profile builder — a suggestion
 * list that arrives a round trip after the field it belongs to is a list
 * nobody uses.
 *
 * The suggestions used to be food and nothing but food: cafe, brunch, bakery,
 * brewery, home chef. We take creators of every category, and that list told
 * a fashion or gaming creator otherwise before they had typed anything. Food
 * is now one group of fifteen rather than the whole taxonomy.
 *
 * `niches` and `genres` are still free text — a creator can type their own —
 * so this is a starting point, not a constraint.
 */

export const CREATOR_TAXONOMY = [
    [
        "Food & Drink",
        ["food", "cafe", "brunch", "bakery", "fine dining", "street food", "coffee", "desserts", "cocktails", "brewery", "home chef", "vegan"],
    ],
    [
        "Fashion",
        ["fashion", "streetwear", "ethnic wear", "thrift", "styling", "luxury"],
    ],
    [
        "Beauty",
        ["beauty", "skincare", "makeup", "haircare", "fragrance", "grooming"],
    ],
    [
        "Travel",
        ["travel", "hotels", "weekend trips", "adventure", "solo travel", "budget travel"],
    ],
    [
        "Fitness & Wellness",
        ["fitness", "gym", "yoga", "running", "nutrition", "mental health"],
    ],
    [
        "Tech",
        ["tech", "gadgets", "phones", "apps", "ai", "photography gear"],
    ],
    [
        "Gaming",
        ["gaming", "esports", "mobile gaming", "streaming", "game reviews"],
    ],
    [
        "Home & Interiors",
        ["home", "interiors", "decor", "diy", "plants", "organisation"],
    ],
    [
        "Parenting",
        ["parenting", "new parents", "kids activities", "family", "baby products"],
    ],
    [
        "Finance",
        ["finance", "investing", "personal finance", "startups", "career"],
    ],
    [
        "Art & Design",
        ["art", "design", "illustration", "crafts", "photography"],
    ],
    [
        "Music",
        ["music", "singing", "instruments", "production", "gigs"],
    ],
    [
        "Comedy",
        ["comedy", "sketch", "standup", "memes", "relatable"],
    ],
    [
        "Automotive",
        ["automotive", "cars", "bikes", "ev", "reviews"],
    ],
    [
        "Pets",
        ["pets", "dogs", "cats", "pet care"],
    ],
];

/** Flat, for a plain suggestion list that has no room for headings. */
export const CREATOR_TAXONOMY_TERMS = CREATOR_TAXONOMY.flatMap(([, terms]) => terms);

/**
 * The cities a creator can pick. Closed on purpose: "Bangalore", "bangalore"
 * and "BLR" are three rows in a filter and one city in reality, and free text
 * meant a brand filtering the directory found a fraction of the people in it.
 */
export const INDIAN_CITIES = [
    "Bengaluru",
    "Mumbai",
    "Delhi NCR",
    "Hyderabad",
    "Chennai",
    "Pune",
    "Kolkata",
    "Ahmedabad",
    "Jaipur",
    "Chandigarh",
    "Kochi",
    "Goa",
    "Lucknow",
    "Indore",
    "Coimbatore",
    "Surat",
    "Nagpur",
    "Bhubaneswar",
    "Guwahati",
    "Dehradun"
];

export const CITY_OPTIONS = INDIAN_CITIES.map((c) => ({ value: c, label: c }));
