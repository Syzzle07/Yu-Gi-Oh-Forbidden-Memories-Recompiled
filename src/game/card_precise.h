#ifndef MEMORIES_GAME_CARD_PRECISE_H
#define MEMORIES_GAME_CARD_PRECISE_H
#ifdef MEMORIES_PC
/* The big card (func_800291E0, drawn by func_80028B08 and its frame plate's
 * DisplayObject_RenderSpriteSheet) scaled: the console rounds every corner
 * the GTE projects to a whole pixel, so a mod's small card, 0.4 say, got
 * digits of uneven height and a name plate of uneven width. A card scaled
 * flat, without a turn about x or y, has one depth for all of it: its pieces
 * go to the picture as the single quad each is, where they are exactly
 * (pgxp.h, Pgxp_CardBegin). A card at full size, a turning one, the software
 * picture and 1x are drawn as retail does. The scope ends in the caller's
 * wrapper (Pgxp_CardEnd).
 *
 * `proj` is the ProjectionOut func_80041F90 just filled: its f4 is how many
 * times DisplayObject_SubmitPacket divides a piece into sub-quads, whose own
 * corners round again. */
#include "display_object.h"
#include "display_object_projection.h"
#include "card_preview_callbacks.h"
#include "pc/compat/pgxp.h"

/* The card's frame plate: what func_800291E0 sets CardPreview_UpdateVariant
 * as the callback of (the card object itself is func_80028B08's). */
static inline int CardPrecise_IsFrame(const DisplayObject *object)
{
    return object->field_10 == (u32)CardPreview_UpdateVariant;
}

static inline int CardPrecise_Begin(const DisplayObject *card, struct ProjectionOut *proj)
{
    if (!Pgxp_CardAllowed) return 0;
    if (card->field_20.b.field_20 || card->field_20.b.field_21) return 0;
    if (card->field_44.h.field_44 == 0x1000 && card->field_44.h.field_46 == 0x1000) return 0;
    Pgxp_CardBegin();
    proj->f4 = 0;
    return 1;
}
#endif
#endif
