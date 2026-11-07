#ifndef MEMORIES_PC_CARD_FOIL_H
#define MEMORIES_PC_CARD_FOIL_H
/* A card's foil finish: a shimmer drawn over the big card (the viewer, the
 * Library, Build Deck's card view), the way a trading card's foil catches the
 * light. A card gets one with "finish" in its manifest entry (notes/more-cards.md):
 *
 *   glossy  a faint rainbow over the picture, and a silver glint that runs from
 *           the card's top-left corner around its edge, both ways, to the
 *           bottom-right, with another doing the same round the picture's edge;
 *   royal   a clear rainbow turning over the whole card, and a band of
 *           prismatic shards in rainbow colours that sweeps from the top-left
 *           to the bottom-right.
 *
 * Both are made of gouraud quads (nothing is drawn from a texture), blended
 * onto the card by addition, and move with the game's VBlank count; the
 * game's drawing (func_80028B08) submits them. No mod with a finish, no
 * change: Cards_Finish is 0 for every card. */

enum {
    CARD_FINISH_NONE = 0,
    CARD_FINISH_GLOSSY,
    CARD_FINISH_ROYAL,
    CARD_FINISH_COUNT
};

/* A gouraud quad as the game's POLY_G4 has it: corners in the order top-left,
 * top-right, bottom-left, bottom-right, each with its colour (what is added
 * to the card; 0 adds nothing). */
typedef struct {
    short x[4], y[4];
    unsigned char r[4], g[4], b[4];
} CardFoilQuad;

typedef struct {
    int x, y, w, h;
} CardFoilRect;

#define CARD_FOIL_MAX 200

/* The quads of `finish` over the card in `card` with its picture in `art`,
 * `ticks` VBlanks into the game, for a card whose colour is `fade` (the
 * card's colour word's red, 128 for none: a card that fades out takes its
 * foil with it). At most `max` of them, in `out`; returns how many. Pure:
 * the same arguments make the same quads. */
int CardFoil_Quads(int finish, const CardFoilRect *card, const CardFoilRect *art, unsigned ticks, int fade,
                   CardFoilQuad *out, int max);

#endif
