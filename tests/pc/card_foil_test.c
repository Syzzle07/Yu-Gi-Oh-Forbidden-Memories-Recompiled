/* A card's foil finish (src/pc/cards/card_foil.c): what it draws over a card, and that it is the same
 * every time, stays on the card, and is turned the way the game's GPU draws. */
#include <stdio.h>
#include <string.h>

#include "pc/cards/card_foil.h"

static int failures;

#define CHECK(condition, ...)                                                                   \
    do {                                                                                        \
        if (!(condition)) {                                                                     \
            fprintf(stderr, "FAIL %s:%d: ", __FILE__, __LINE__);                                \
            fprintf(stderr, __VA_ARGS__);                                                       \
            fputc('\n', stderr);                                                                \
            failures++;                                                                         \
        }                                                                                       \
    } while (0)

static const CardFoilRect card = {10, 20, 140, 192};
static const CardFoilRect art = {10 + 0x13, 20 + 0x32, 0x66, 0x60};

static int lit(const CardFoilQuad *q)
{
    int i, most = 0;
    for (i = 0; i < 4; i++) {
        if (q->r[i] > most) most = q->r[i];
        if (q->g[i] > most) most = q->g[i];
        if (q->b[i] > most) most = q->b[i];
    }
    return most;
}

/* The first triangle of the quad runs the way the game's top-left, top-right, bottom-left does. */
static int turned_right(const CardFoilQuad *q)
{
    return (q->x[1] - q->x[0]) * (q->y[2] - q->y[0]) - (q->y[1] - q->y[0]) * (q->x[2] - q->x[0]) > 0;
}

int main(void)
{
    static CardFoilQuad a[CARD_FOIL_MAX], b[CARD_FOIL_MAX];
    unsigned ticks;
    int finish, i, n, m, most_glossy = 0, most_royal = 0, rest_glossy = 0, band_royal = 0;

    CHECK(CardFoil_Quads(CARD_FINISH_NONE, &card, &art, 0, 128, a, CARD_FOIL_MAX) == 0, "no finish draws nothing");
    CHECK(CardFoil_Quads(CARD_FINISH_ROYAL, &card, NULL, 0, 128, a, CARD_FOIL_MAX) == 0, "no picture, no foil");

    for (finish = CARD_FINISH_GLOSSY; finish <= CARD_FINISH_ROYAL; finish++) {
        for (ticks = 0; ticks < 1200; ticks += 7) {
            n = CardFoil_Quads(finish, &card, &art, ticks, 128, a, CARD_FOIL_MAX);
            m = CardFoil_Quads(finish, &card, &art, ticks, 128, b, CARD_FOIL_MAX);
            CHECK(n > 0 && n <= CARD_FOIL_MAX, "finish %d at %u: %d quads", finish, ticks, n);
            CHECK(n == m && !memcmp(a, b, sizeof(a[0]) * (size_t)n), "finish %d at %u: not the same twice", finish, ticks);
            for (i = 0; i < n; i++) {
                int k;
                CHECK(turned_right(&a[i]), "finish %d at %u: quad %d is turned the wrong way", finish, ticks, i);
                for (k = 0; k < 4; k++) {
                    CHECK(a[i].x[k] >= card.x - 1 && a[i].x[k] <= card.x + card.w + 1 &&
                              a[i].y[k] >= card.y - 1 && a[i].y[k] <= card.y + card.h + 1,
                          "finish %d at %u: quad %d corner %d is off the card (%d,%d)", finish, ticks, i, k,
                          a[i].x[k], a[i].y[k]);
                }
                if (finish == CARD_FINISH_GLOSSY && lit(&a[i]) > most_glossy) most_glossy = lit(&a[i]);
                if (finish == CARD_FINISH_ROYAL && lit(&a[i]) > most_royal) most_royal = lit(&a[i]);
            }
            if (finish == CARD_FINISH_GLOSSY && ticks % 270 >= 200) rest_glossy = rest_glossy < n ? n : rest_glossy;
            if (finish == CARD_FINISH_ROYAL && n > 48) band_royal = 1;
        }
    }
    CHECK(most_glossy >= 150, "the glint is bright: %d", most_glossy);
    CHECK(most_royal >= 100, "the shards are bright: %d", most_royal);
    CHECK(rest_glossy <= 36, "between glints only the faint rainbow: %d quads", rest_glossy);
    CHECK(band_royal, "the shard band shows");

    /* A card that fades out takes its foil with it. */
    n = CardFoil_Quads(CARD_FINISH_ROYAL, &card, &art, 40, 128, a, CARD_FOIL_MAX);
    m = CardFoil_Quads(CARD_FINISH_ROYAL, &card, &art, 40, 0, b, CARD_FOIL_MAX);
    CHECK(n == m && n > 0, "same quads");
    for (i = 0; i < m; i++) CHECK(lit(&b[i]) == 0, "faded out: quad %d still lit", i);

    /* Room for fewer quads than it makes: it stops at the room. */
    CHECK(CardFoil_Quads(CARD_FINISH_ROYAL, &card, &art, 40, 128, a, 5) == 5, "at most max");

    if (failures) return 1;
    puts("Card foil: the finishes are as expected");
    return 0;
}
