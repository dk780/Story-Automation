"""Accurate, respectful iconography for the Hindu deities and other mythological characters, so the pictures stay
recognisable and consistent no matter how the AI describes them."""
import re

BASE = "stylized 3D animated character, expressive face, "
DEITIES = [
    # (keywords, adult look, child look)
    (["krishna", "कृष्ण", "कान्हा", "कन्हैया", "गोपाल", "kanha"],
     "Lord Krishna, a handsome divine youth with deep blue skin, a peacock feather in his golden crown, holding a bamboo flute, yellow silk dhoti, garland of forest flowers, gentle mischievous smile, large lotus-shaped eyes, soft golden glow",
     "child Krishna (Bal Gopal), an adorable chubby little boy with deep blue skin, curly dark hair, a small peacock feather, butter smeared on his cheeks, tiny golden ornaments, mischievous twinkling eyes"),
    (["shiva", "शिव", "mahadev", "महादेव", "shankar", "शंकर", "bholenath", "भोलेनाथ"],
     "Lord Shiva, serene ascetic god with pale ash-smeared skin and a blue throat, a third eye on his forehead, matted hair with a crescent moon and the River Ganga flowing from it, a serpent around his neck, tiger-skin garment, holding a trident with a damaru, calm powerful presence",
     None),
    (["parvati", "पार्वती", "gauri", "गौरी", "uma", "उमा"],
     "Goddess Parvati, graceful and radiant, in a red and gold silk saree with gold jewellery, a red bindi and a lotus, kind strong eyes, soft divine glow", None),
    (["ganesha", "ganesh", "गणेश", "गणपति", "ganapati", "vinayak", "विनायक"],
     "Lord Ganesha, the elephant-headed god with a big round belly, one broken tusk, four arms holding a modak, an axe, a lotus and a blessing hand, golden crown, red and yellow silk, wise kind eyes, a small mouse beside him",
     "child Ganesha (Bal Ganesh), an adorable chubby little elephant-headed boy with big gentle eyes, one small tusk, a small golden crown, holding a modak, a tiny mouse beside him"),
    (["hanuman", "हनुमान", "bajrang", "बजरंग", "maruti", "मारुति", "anjaneya"],
     "Lord Hanuman, mighty monkey god with golden-orange fur and a red face, a golden crown and earrings, holding a mace (gada), saffron dhoti, strong chest, long tail, devoted loving eyes",
     "baby Hanuman (Bal Hanuman), an adorable chubby baby monkey boy with golden-orange fur, a tiny gold waist-cord and earrings, huge curious amber eyes, a small curling tail"),
    (["vishnu", "विष्णु", "narayan", "नारायण", "hari", "हरि"],
     "Lord Vishnu, calm divine god with blue skin and four arms holding a conch, the Sudarshana discus, a mace and a lotus, golden crown, yellow silk dhoti, Kaustubha gem on his chest, serene smile", None),
    (["lakshmi", "लक्ष्मी"],
     "Goddess Lakshmi, golden-complexioned goddess seated on a pink lotus, holding lotus flowers with gold coins falling from her hand, red and gold saree, jewellery, gentle smile", None),
    (["durga", "दुर्गा", "ambe", "अम्बे", "mahadevi", "devi", "देवी"],
     "Goddess Durga, radiant warrior goddess with ten arms each holding a divine weapon, red saree, golden crown, fierce compassionate eyes, riding a majestic lion, glowing aura", None),
    (["annapurna", "अन्नपूर्णा"],
     "Goddess Annapurna, warm motherly goddess in a red and gold saree holding a golden ladle and a vessel of food, kind smiling face, divine glow", None),
    (["saraswati", "सरस्वती"],
     "Goddess Saraswati, serene goddess in a white saree playing a veena, seated on a white lotus with a swan beside her, calm wise eyes", None),
    (["brahma", "ब्रह्मा"],
     "Lord Brahma, ancient four-faced god with a long white beard, seated on a lotus, holding a scripture and a water pot, calm wise expression", None),
    (["ram", "राम", "rama", "raghav", "रघुनंदन"],
     "Lord Rama, noble and serene prince with dark blue-green skin, a golden crown, holding a great bow and arrows, saffron and yellow silk, calm compassionate eyes, soft divine glow", None),
    (["sita", "सीता"],
     "Goddess Sita, graceful and gentle princess in a yellow and green silk saree with gold jewellery, a kind radiant face, a small bindi", None),
    (["lakshman", "लक्ष्मण"],
     "Lakshmana, loyal young warrior prince with golden-brown skin, a bow and quiver, simple saffron clothes, determined eyes", None),
    (["narasimha", "नरसिंह"],
     "Lord Narasimha, divine half-man half-lion with a golden mane, glowing fierce eyes and sharp claws, powerful muscular body, a divine blazing aura", None),
    (["prahlad", "प्रह्लाद", "prahlada"],
     "Prahlad, a small gentle boy devotee with folded hands, a sacred tilak on his forehead, simple orange dhoti, peaceful glowing face", None),
    (["hiranyakashipu", "हिरण्यकशिपु", "hiranyakashyap"],
     "Hiranyakashipu, arrogant demon king with a huge muscular body, a golden crown and armour, fierce red eyes and sharp tusks", None),
    (["vamana", "वामन"],
     "Lord Vamana, a small radiant Brahmin boy holding an umbrella and a water pot, a sacred thread, calm smiling face with a divine glow", None),
    (["bali", "बलि"],
     "King Bali, generous and mighty demon king with a golden crown, rich royal robes, a noble kind face", None),
    (["indra", "इंद्र", "इन्द्र"],
     "Lord Indra, king of the gods with a jewelled golden crown, holding the vajra thunderbolt, rich blue and gold robes, regal expression, storm clouds around him", None),
    (["yama", "यम", "yamraj", "यमराज"],
     "Lord Yama, god of death, dark-skinned and stern with a tall dark crown, a noose in his hand, riding a great black buffalo, solemn eyes", None),
    (["markandeya", "मार्कंडेय"],
     "Markandeya, a young sage boy with long hair, a rudraksha garland, ash on his forehead, hands folded in deep devotion", None),
    (["bhagiratha", "भगीरथ"],
     "King Bhagiratha, an ascetic king with a determined peaceful face, simple saffron robes and a rudraksha garland, in deep penance", None),
    (["yashoda", "यशोदा"],
     "Mother Yashoda, a kind loving village woman in a simple colourful saree with silver jewellery, warm smiling eyes", None),
    (["nanda", "नंद"],
     "Nanda Baba, a gentle cow-herd chief with a turban and a white moustache, simple village clothes, kind eyes", None),
    (["radha", "राधा"],
     "Radha, a graceful divine maiden in a blue and pink lehenga with flowers in her hair, glowing devoted eyes", None),
    (["sudama", "सुदामा"],
     "Sudama, a thin poor Brahmin in a worn white dhoti, carrying a small bundle of flattened rice, kind humble eyes", None),
    (["kamsa", "कंस"],
     "King Kamsa, cruel tyrant king with a dark crown, heavy armour and a harsh scowl", None),
    (["kaliya", "कालिय"],
     "Kaliya, a giant black multi-headed serpent with glowing eyes rising from the river Yamuna", None),
    (["narada", "नारद"],
     "Sage Narada, a cheerful wandering sage with a veena and cymbals, a sacred tilak, a white dhoti and a happy glowing face", None),
    (["kartikeya", "कार्तिकेय", "murugan", "मुरुगन"],
     "Lord Kartikeya, a handsome young warrior god riding a peacock, holding a divine spear (vel), golden crown, radiant face", None),
    (["savitri", "सावित्री"],
     "Savitri, a devoted and courageous young wife in a simple red saree with a determined glowing face", None),
    (["satyavan", "सत्यवान"],
     "Satyavan, a kind young woodcutter prince in simple forest clothes carrying an axe", None),
    (["garuda", "गरुड़"],
     "Garuda, a majestic golden eagle-man with huge wings and a sharp beak, a golden crown", None),
    (["mahishasura", "महिषासुर"],
     "Mahishasura, a mighty demon with a buffalo head and a huge dark muscular body, armour and a mace", None),
]
CHILD_WORDS = ["bal ", "baby", "child", "little", "young", "बाल", "नन्हे", "नन्हा", "छोटे", "लल्ला", "कान्हा", "bal_"]


def canonical_look(name, given):
    """Return the standard iconography for known deities; keep the AI's own description for everyone else."""
    n = f" {name.lower().strip()} "
    for kws, adult, child in DEITIES:
        if any(re.search(rf"(?<![a-z]){re.escape(k.lower())}(?![a-z])", n) if k.isascii() else k in n for k in kws):
            g = (given or "").lower()
            is_child = any(w in n for w in CHILD_WORDS) or name.lower().startswith("bal") or \
                any(w in g for w in ["baby", "toddler", "infant", "little boy", "small boy", "young boy", "chubby", "child"])
            return BASE + (child if (is_child and child) else adult)
    return BASE + given if given and not given.lower().startswith("stylized") else given
