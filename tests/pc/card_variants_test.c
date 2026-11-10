/* Variants of a retail card (notes/more-cards.md, "Variants"): a copy with a
 * "variant_permille" is the card's alternate version, won in its place by a
 * chance of its own. The real mod loader finds one mod in a scratch folder and
 * cards.c's Cards_Build reads it through Mods_VisitCards, on a stand-in for the
 * disc's tables. Checks the family index, what a bad entry is told, the roll
 * (each variant by its chance, one random number apiece, none for a card
 * without variants or for the CPU when a variant did not ask), and the
 * family's copy count for the deck limit.
 *
 * Mods_Load and Cards_Build run once a process, so this is one run. */
#define _POSIX_C_SOURCE 200809L /* before any header: cards.c's strdup */
#include <stdint.h>

/* The disc's tables, here. cards.c reads them at fixed addresses. */
static unsigned test_stats[722];
static short test_sort_keys[722];
static unsigned char test_level_attr[723];
static unsigned short test_name_offsets[723];
static unsigned char test_text_bank[16] = {0xFF};
static unsigned test_glyphs[256];
#define RETAIL_STATS ((uintptr_t)test_stats)
#define RETAIL_SORT_KEYS ((uintptr_t)test_sort_keys)
#define RETAIL_LEVEL_ATTR ((uintptr_t)test_level_attr)
#define RETAIL_NAME_OFFSETS ((uintptr_t)test_name_offsets)
#define TEXT_BANK ((uintptr_t)test_text_bank)
#define GLYPH_TABLE ((uintptr_t)test_glyphs)

#include "../../src/pc/cards/cards.c"
#include "pc/debug/symbols.h"
#include "pc/mods/exports.h"
#include "scratch.h"
#include <assert.h>
#include <sys/stat.h>
#include <unistd.h>

int gCard_nCount = CARD_COUNT, gCard_nExtraOwner;
unsigned short gCard_awBaseId[CARD_TABLE_ID_END], gDuel_awPlayerDeck[1024];
unsigned char gCard_abExtraChest[CARD_TABLE_ID_END], gCard_abExtraSeen[(CARD_TABLE_ID_END + 7) / 8];
unsigned char gCard_abPairChest[2][CARD_TABLE_ID_END], gCard_abPairPending[2][CARD_TABLE_ID_END];
int gDuel_adwCardStats[CARD_TABLE_ID_END];
short gCard_asNameSortKey[CARD_TABLE_ID_END];
unsigned char gDuel_abCardLevelAttr[CARD_TABLE_ID_END];

/* --- what the mod loader reaches (as tests/pc/mods_test.c) ------------ */

int Log_Enabled(LogChannel channel) { (void)channel; return 0; }
int Log_Wanted(LogChannel channel) { (void)channel; return 0; }
void Log_Printf(LogChannel channel, const char *format, ...) { (void)channel; (void)format; }
unsigned short Platform_Pad(int port) { (void)port; return 0; }
int Symbols_Add(const SymbolsEntry *entries, size_t count) { (void)entries; (void)count; return 0; }
int Memories_DiscReadSectors(int lba, int sectors, void *out)
{
    (void)lba;
    memset(out, 0, (size_t)sectors * 2048);
    return sectors;
}
int Memories_DiscSectorCount(void) { return 10000; }
int Memories_DiscOriginalFileInfo(const char *path, int *lba, unsigned *size)
{
    (void)path; (void)lba; (void)size;
    return -1;
}
int Memories_DiscFileInfo(const char *path, int *lba, unsigned *size)
{
    (void)path; (void)lba; (void)size;
    return -1;
}
int Memories_DiscFileStart(const char *path) { (void)path; return -1; }
const MemoriesModExport Memories_ModExports[] = {{"D_80010000", (void *)0x80010000u}};
const unsigned Memories_ModExportCount = 1;

/* --- what cards.c reaches that these checks never get to -------------- */

int Campaign_TestStoryFlag(int flag) { (void)flag; return 0; }
int CardArt_Crop(const char *path, int w, int h, int *x, int *y, int *cw, int *ch, int *width, int *height)
{
    (void)path; (void)w; (void)h; (void)x; (void)y; (void)cw; (void)ch; (void)width; (void)height;
    return 0;
}
int CardArt_FromImage(const char *path, unsigned char *record, char *why, size_t why_size)
{
    (void)path; (void)record; (void)why; (void)why_size;
    return 0;
}
int CardArt_FromImageSeeThrough(const char *path, unsigned char *record, char *why, size_t why_size)
{
    (void)path; (void)record; (void)why; (void)why_size;
    return 0;
}
int CardArt_ThumbnailFromImageSeeThrough(const char *path, unsigned char *record, char *why, size_t why_size)
{
    (void)path; (void)record; (void)why; (void)why_size;
    return 0;
}
int CardArt_HasHoles(const char *path)
{
    (void)path;
    return 0;
}
int CardArt_ThumbnailFromImage(const char *path, unsigned char *record, char *why, size_t why_size)
{
    (void)path; (void)record; (void)why; (void)why_size;
    return 0;
}
int CardArt_FieldArtFromImage(const char *path, unsigned char *record, char *why, size_t why_size)
{
    (void)path; (void)record; (void)why; (void)why_size;
    return 0;
}
int CardArt_TitleFromImage(const char *path, unsigned char *plate, char *why, size_t why_size)
{
    (void)path; (void)plate; (void)why; (void)why_size;
    return 0;
}
int CardArt_TitleFromName(const char *name, unsigned char *plate) { (void)name; (void)plate; return 0; }
int CardLayout_FullBleed(void) { return 0; }
int CardLayout_StyleOf(int card_id, CardLayoutStyle *style) { (void)card_id; (void)style; return 0; }
void CardLayoutArt_Prewarm(void) {}
int CardNotes_Tag(const char *text, const char *key, char *out, size_t size)
{
    (void)text; (void)key; (void)out; (void)size;
    return 0;
}
void Duelists_Build(void) {}
uint32_t Glyphs_Character(int code) { return (uint32_t)code; }
int Glyphs_Code(uint32_t character) { return character < 0x80 ? (int)character : -1; }
uint32_t Glyphs_NextCharacter(const char **text) { return (unsigned char)*(*text)++; }
void Library_UpdateCardUsedFlag(int flag) { (void)flag; }
void Starter_Build(void) {}
void Packs_Build(void) {}
void Tower_Build(void) {}
const UiConfig *UiConfig_Load(void) { return NULL; }
unsigned Packs_Signature(void) { return 0; }
void Tables_Build(void) {}
long Tables_Limit(const char *name) { (void)name; return -1; }
int Tables_StatCapEither(void) { return 9999; }
int Text_Overridden(int id) { (void)id; return 0; }
const unsigned char *Text_Resolve(int id, const unsigned char *retail) { (void)id; return retail; }
void TextureDump_Written(const void *destination, unsigned bytes) { (void)destination; (void)bytes; }
int TexturePack_AddMade(const void *pixels, int words, int rows, int bpp, const void *clut, int clut_entries,
                        const char *file, int x, int y, int w, int h)
{
    (void)pixels; (void)words; (void)rows; (void)bpp; (void)clut; (void)clut_entries; (void)file;
    (void)x; (void)y; (void)w; (void)h;
    return 0;
}
int TexturePack_AddMadeSeeThrough(const void *pixels, int words, int rows, int bpp, const void *clut,
                                  int clut_entries, const char *file, int x, int y, int w, int h)
{
    (void)pixels; (void)words; (void)rows; (void)bpp; (void)clut; (void)clut_entries; (void)file;
    (void)x; (void)y; (void)w; (void)h;
    return 0;
}
int Language_Current(void) { return 0; }
const char *Language_Code(int which) { (void)which; return "en-us"; }
/* The custom type icon bank (type_icons.c): neither mod here declares a
 * "card_types" icon, so a no-op stands in for it. */
void TypeIcons_Clear(void) {}

/* --- fixtures -------------------------------------------------------- */

static char root[SCRATCH_MAX];

static void write_text(const char *relative, const char *text)
{
    char path[2048];
    FILE *file;
    snprintf(path, sizeof(path), "%s/%s", root, relative);
    file = fopen(path, "wb");
    assert(file);
    assert(fwrite(text, 1, strlen(text), file) == strlen(text));
    assert(!fclose(file));
}

static void make_dir(const char *relative)
{
    char path[2048];
    snprintf(path, sizeof(path), "%s/%s", root, relative);
    assert(!mkdir(path, 0777));
}

/* The random numbers the roll asks for, in the order the test queues them. */
static int rand_queue[4], rand_length, rand_position, rand_draws;

int Memories_Rand(void)
{
    rand_draws++;
    return rand_position < rand_length ? rand_queue[rand_position++] : 0;
}

static void rolls(int count, int first, int second)
{
    rand_queue[0] = first;
    rand_queue[1] = second;
    rand_length = count;
    rand_position = 0;
    rand_draws = 0;
}

static unsigned char quantities[CARD_TABLE_ID_END];

int main(void)
{
    char path[2048];
    const char *notes;
    int id;
    /* Every card of the disc a monster of 1000 ATK. */
    for (id = 1; id <= CARD_COUNT; id++) test_stats[id - 1] = 100u;

    assert(scratch_dir(root, sizeof(root), "memories-card-variants"));
    make_dir("mods");
    make_dir("mods/cardvariants");
    /* Card 1 has two variants, 5% and 20%; card 2 a plain copy that shares
     * its drops evenly (the older way); card 17 (a piece of Exodia), a chance
     * of 0 and of 1001, a label with no chance and a replace with variant keys
     * are all noted and left out; card 5 has a variant the CPU rolls too; card
     * 7 one with a label longer than the 24 letters kept. "own" is a card of the mod's own; "ownalt" a variant of it
     * (its "copy" is its identity), "nested" one of a variant and "lost" one of a card nothing added. The variants
     * are made after every other card, in file order. */
    write_text("mods/cardvariants/mod.json",
               "{\"id\":\"cardvariants\",\"cards\":["
               "{\"copy\":1,\"id\":\"alt1\",\"variant_permille\":50,\"variant_label\":\"Rainbow foil\"},"
               "{\"copy\":1,\"id\":\"alt2\",\"variant_permille\":200},"
               "{\"copy\":2,\"id\":\"share\"},"
               "{\"copy\":17,\"id\":\"exodia\",\"variant_permille\":100},"
               "{\"copy\":3,\"id\":\"zero\",\"variant_permille\":0},"
               "{\"copy\":3,\"id\":\"huge\",\"variant_permille\":1001},"
               "{\"copy\":5,\"id\":\"cpu\",\"variant_permille\":1000,\"opponents\":true},"
               "{\"copy\":6,\"id\":\"label\",\"variant_label\":\"Alone\"},"
               "{\"copy\":7,\"id\":\"long\",\"variant_permille\":10,\"variant_label\":\"0123456789012345678901234567890\"},"
               "{\"replace\":4,\"variant_permille\":10},"
               "{\"copy\":9,\"id\":\"own\",\"name\":\"Own\",\"description\":\"Its own words.\"},"
               "{\"copy\":\"cardvariants:own\",\"id\":\"ownalt\",\"variant_permille\":300,\"variant_label\":\"Own alt\"},"
               "{\"copy\":\"cardvariants:alt1\",\"id\":\"nested\",\"variant_permille\":100},"
               "{\"copy\":\"cardvariants:nothing\",\"id\":\"lost\",\"variant_permille\":100}]}");
    write_text("settings.txt", "mod.cardvariants=1\n");
    snprintf(path, sizeof(path), "%s/mods", root);
    assert(!setenv("MEMORIES_MODS_DIR", path, 1));
    snprintf(path, sizeof(path), "%s/settings.txt", root);
    assert(!setenv("MEMORIES_SETTINGS", path, 1));
    assert(!setenv("MEMORIES_USER_DIR", root, 1));
    Settings_Load();
    Mods_Load();
    assert(Mods_LoadedCount() == 1);

    Cards_Build();

    /* The cards that are not variants first: share 723, label 724, own 725; then the variants, in file order: alt1 726,
     * alt2 727, exodia 728, zero 729, huge 730, cpu 731, long 732, ownalt 733, nested 734. "lost" is no card. */
    assert(gCard_nCount == CARD_COUNT + 12);
    assert(Cards_VariantOf(726) == 1 && Cards_VariantOf(727) == 1);
    assert(Cards_VariantOf(723) == 0);   /* a plain copy is not a variant */
    assert(Cards_VariantOf(728) == 0 && Cards_VariantOf(729) == 0 && Cards_VariantOf(730) == 0);
    assert(Cards_VariantOf(731) == 5 && Cards_VariantOf(724) == 0 && Cards_VariantOf(732) == 7);
    assert(Cards_VariantOf(1) == 0 && Cards_VariantOf(0) == 0 && Cards_VariantOf(gCard_nCount + 1) == 0);
    assert(Cards_BaseId(726) == 1 && Cards_BaseId(731) == 5);
    /* A variant of a card a mod added: its base is that card, and what it is a copy of is that card's. */
    assert(Cards_VariantOf(733) == 725 && Cards_BaseId(733) == 9 && Cards_BaseId(725) == 9);
    assert(Cards_VariantOf(734) == 0);   /* a variant cannot copy a variant: it is no variant */

    /* The family index, in card order. */
    assert(Cards_VariantCount(1) == 2 && Cards_VariantMember(1, 0) == 726 && Cards_VariantMember(1, 1) == 727);
    assert(Cards_VariantMember(1, 2) == 0 && Cards_VariantMember(1, -1) == 0);
    assert(Cards_VariantCount(2) == 0 && Cards_VariantCount(17) == 0 && Cards_VariantCount(0) == 0);
    assert(Cards_VariantCount(5) == 1 && Cards_VariantCount(7) == 1 && Cards_VariantCount(726) == 0);
    assert(Cards_VariantCount(725) == 1 && Cards_VariantMember(725, 0) == 733 && Cards_VariantMember(725, 1) == 0);
    assert(Cards_VariantCount(gCard_nCount + 1) == 0 && Cards_VariantCount(CARD_TABLE_ID_END) == 0);
    assert(Cards_VariantPermille(726) == 50 && Cards_VariantPermille(727) == 200 && Cards_VariantPermille(1) == 0);
    assert(Cards_VariantPermille(733) == 300);
    assert(Cards_VariantLabel(726) && !strcmp(Cards_VariantLabel(726), "Rainbow foil"));
    assert(Cards_VariantLabel(733) && !strcmp(Cards_VariantLabel(733), "Own alt"));
    assert(!Cards_VariantLabel(727) && !Cards_VariantLabel(1));
    assert(Cards_VariantLabel(732) && strlen(Cards_VariantLabel(732)) == 24);
    /* It has the name and the words of the card it is a variant of. */
    assert(Cards_NameText(733) && Cards_NameText(733) == Cards_NameText(725));
    assert(Cards_DescriptionText(733) && Cards_DescriptionText(733) == Cards_DescriptionText(725));
    assert(!Cards_NameText(726));   /* a variant of a card of the disc has the disc's */

    /* What the mod's author is told. */
    notes = Mods_Status(Mods_Loaded(0));
    assert(strstr(notes, "not a piece of Exodia"));
    assert(strstr(notes, "cannot copy a variant"));   /* (the Mods window's text is cut: the last note is in the log) */
    assert(strstr(notes, "thousandths, 1 to 1000"));
    assert(strstr(notes, "needs \"variant_permille\""));
    assert(strstr(notes, "cut to 24 letters"));
    assert(strstr(notes, "belong to a \"copy\" entry"));

    /* A roll of card 1: each variant by its chance, in order, one number each. */
    rolls(2, 500, 100);
    assert(Cards_PickVariant(1, CARDS_USE_DROP) == 727 && rand_draws == 2);
    rolls(1, 10, 0);
    assert(Cards_PickVariant(1, CARDS_USE_DROP) == 726 && rand_draws == 1);
    rolls(2, 50, 199);   /* 50 is not under 5%; 199 is under 20% */
    assert(Cards_PickVariant(1, CARDS_USE_DROP) == 727 && rand_draws == 2);
    rolls(2, 999, 999);
    assert(Cards_PickVariant(1, CARDS_USE_DROP) == 1 && rand_draws == 2);
    /* The CPU's deals: card 1's variants did not ask, so no number is drawn. */
    rolls(2, 0, 0);
    assert(Cards_PickVariant(1, CARDS_USE_OPPONENT) == 1 && rand_draws == 0);
    rolls(1, 999, 0);
    assert(Cards_PickVariant(5, CARDS_USE_OPPONENT) == 731 && rand_draws == 1);
    rolls(1, 999, 0);
    assert(Cards_PickVariant(5, CARDS_USE_DROP) == 731 && rand_draws == 1);
    rolls(1, 5, 0);
    assert(Cards_PickVariant(7, CARDS_USE_DROP) == 732);
    rolls(1, 10, 0);
    assert(Cards_PickVariant(7, CARDS_USE_DROP) == 7);

    /* A card with no variant draws nothing, as before; the older even share
     * of a plain copy still works (one number, picking among two). */
    rolls(1, 0, 0);
    assert(Cards_PickVariant(8, CARDS_USE_DROP) == 8 && rand_draws == 0);
    rolls(1, 1, 0);
    assert(Cards_PickVariant(2, CARDS_USE_DROP) == 723 && rand_draws == 1);
    rolls(1, 0, 0);
    assert(Cards_PickVariant(2, CARDS_USE_DROP) == 2 && rand_draws == 1);
    /* A copy that is no variant is never rolled as a base: its id comes back. */
    rolls(1, 0, 0);
    assert(Cards_PickVariant(723, CARDS_USE_DROP) == 723 && rand_draws == 0);
    /* A card a mod added is rolled for its variants, each by its chance, as a card of the disc is. */
    rolls(1, 299, 0);
    assert(Cards_PickVariant(725, CARDS_USE_DROP) == 733 && rand_draws == 1);
    rolls(1, 300, 0);
    assert(Cards_PickVariant(725, CARDS_USE_DROP) == 725 && rand_draws == 1);
    rolls(1, 0, 0);   /* the CPU's deals: this variant did not ask */
    assert(Cards_PickVariant(725, CARDS_USE_OPPONENT) == 725 && rand_draws == 0);
    /* And an id past the mods' cards, or a variant, is not one. */
    rolls(1, 0, 0);
    assert(Cards_PickVariant(gCard_nCount + 1, CARDS_USE_DROP) == gCard_nCount + 1 && rand_draws == 0);
    assert(Cards_PickVariant(733, CARDS_USE_DROP) == 733 && rand_draws == 0);

    /* A deck holds the limit of a card and its variants together. */
    quantities[1] = 1;
    quantities[726] = 2;
    assert(Cards_FamilyCopies(quantities, 1) == 3);
    assert(Cards_FamilyCopies(quantities, 726) == 3);
    assert(Cards_FamilyCopies(quantities, 727) == 3);
    quantities[2] = 2;
    quantities[723] = 1;
    assert(Cards_FamilyCopies(quantities, 2) == 2);   /* an even-share copy is its own card */
    quantities[8] = 1;
    assert(Cards_FamilyCopies(quantities, 8) == 1);
    /* A card a mod added and its variant too. */
    quantities[725] = 1;
    quantities[733] = 2;
    assert(Cards_FamilyCopies(quantities, 725) == 3 && Cards_FamilyCopies(quantities, 733) == 3);

    /* The Library's cells (SET_LIBRARY_FOLD_VARIANTS is on unless the player turns it off): every card but the
     * variants, in card order, so 5 of the 734 cards share a cell. */
    Cards_LibraryBegin();
    assert(Cards_LibraryFolded());
    assert(Cards_LibraryEntryCount() == gCard_nCount - 5);
    assert(Cards_LibraryEntry(0) == 0 && Cards_LibraryEntry(1) == 1 && Cards_LibraryEntry(722) == 722);
    /* The cards of the mod follow the disc's: no cell is empty, and the variants' ids (last) leave none. */
    assert(Cards_LibraryEntry(723) == 723 && Cards_LibraryEntry(724) == 724 && Cards_LibraryEntry(725) == 725);
    assert(Cards_LibraryEntry(726) == 728 && Cards_LibraryEntry(727) == 729 && Cards_LibraryEntry(728) == 730);
    assert(Cards_LibraryEntry(729) == 734 && Cards_LibraryEntry(730) == 0);   /* the variants share their cards' cells */
    assert(Cards_LibraryEntry(-1) == 0 && Cards_LibraryEntry(9999) == 0);
    /* The entry is seen once any of its cards is; its cards shown are the card, then each variant seen. */
    assert(!Cards_LibraryFamilySeen(1) && Cards_LibraryFamilySize(1) == 1);
    assert(Cards_LibraryFamilyMember(1, 0) == 1 && Cards_LibraryFamilyMember(1, 1) == 0);
    Cards_MarkSeen(727);
    assert(Cards_LibraryFamilySeen(1) && Cards_LibraryFamilySeen(5) == 0);
    assert(Cards_LibraryFamilySize(1) == 2 && Cards_LibraryFamilyMember(1, 1) == 727);
    Cards_MarkSeen(726);
    assert(Cards_LibraryFamilySize(1) == 3 && Cards_LibraryFamilyMember(1, 1) == 726 &&
           Cards_LibraryFamilyMember(1, 2) == 727 && Cards_LibraryFamilyMember(1, 3) == 0);
    assert(Cards_LibraryFamilySize(2) == 1);   /* a card with no variants is its own entry */
    /* An entry of a card a mod added: its variant is seen, then shown, as a card of the disc's. */
    assert(!Cards_LibraryFamilySeen(725) && Cards_LibraryFamilySize(725) == 1);
    Cards_MarkSeen(733);
    assert(Cards_LibraryFamilySeen(725) && Cards_LibraryFamilySize(725) == 2 && Cards_LibraryFamilyMember(725, 1) == 733);
    /* The line about the variants: made for the card on show, as the text of its own string. */
    Cards_LibraryVariantNote(727, 1);
    assert(Cards_Text(LIBRARY_VARIANT_TEXT_ID, NULL));   /* (the glyphs of the line are the game's: not checked here) */
    assert(!Cards_Text(0x10, NULL));
    /* Turned off: every card has a cell of its own, as before there were variants. */
    Settings_Set(SET_LIBRARY_FOLD_VARIANTS, 0);
    Cards_LibraryBegin();
    assert(!Cards_LibraryFolded() && Cards_LibraryEntryCount() == gCard_nCount);
    assert(Cards_LibraryEntry(734) == 734 && Cards_LibraryEntry(735) == 0 && Cards_LibraryFamilySize(1) == 1);
    Settings_Set(SET_LIBRARY_FOLD_VARIANTS, 1);
    Cards_LibraryBegin();
    assert(Cards_LibraryEntryCount() == gCard_nCount - 5);

    printf("card variants: ok\n");
    return 0;
}
