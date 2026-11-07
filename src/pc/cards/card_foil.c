#include "card_foil.h"

#include <math.h>
#include <string.h>

#define GLOSS_CYCLE 270     /* VBlanks from one glint's start to the next's */
#define GLOSS_SWEEP 110     /* VBlanks a glint takes to run its way */
#define GLOSS_TAIL 0.42f    /* how much of the way (0 to 1) the glint's tail trails behind its head */
#define ROYAL_CYCLE 260
#define ROYAL_SWEEP 170
#define SHARD_COLUMNS 5
#define SHARD_ROWS 7

typedef struct {
    CardFoilQuad *out;
    int count, max;
    int scale; /* 0-256, the card's own fade */
} Sink;

static unsigned hash(unsigned a, unsigned b, unsigned c)
{
    unsigned h = a * 374761393u + b * 668265263u + c * 2246822519u;
    h = (h ^ (h >> 13)) * 1274126177u;
    return h ^ (h >> 16);
}

static float unit(unsigned a, unsigned b, unsigned c)
{
    return (float)(hash(a, b, c) & 0xFFFF) / 65535.0f;
}

static unsigned char byte_of(float value, int scale)
{
    int v = (int)(value * (float)scale / 256.0f + 0.5f);
    return (unsigned char)(v < 0 ? 0 : v > 255 ? 255 : v);
}

/* A colour of the rainbow: `hue` in turns, full saturation, `value` 0-255. */
static void rainbow(float hue, float value, float *r, float *g, float *b)
{
    float h = (hue - floorf(hue)) * 6.0f, f = h - floorf(h);
    switch ((int)h % 6) {
    case 0: *r = 1; *g = f; *b = 0; break;
    case 1: *r = 1 - f; *g = 1; *b = 0; break;
    case 2: *r = 0; *g = 1; *b = f; break;
    case 3: *r = 0; *g = 1 - f; *b = 1; break;
    case 4: *r = f; *g = 0; *b = 1; break;
    default: *r = 1; *g = 0; *b = 1 - f; break;
    }
    *r *= value;
    *g *= value;
    *b *= value;
}

typedef struct {
    float x, y;
    float r, g, b;
} Corner;

/* A quad (corners as the GPU's order: top-left, top-right, bottom-left,
 * bottom-right) of the sink. The game draws a quad whose first triangle is
 * turned one way; a quad built the other way round is mirrored to be that way
 * (its colours stay with their corners). */
static void quad(Sink *sink, Corner c0, Corner c1, Corner c2, Corner c3)
{
    CardFoilQuad *q;
    Corner *corner[4];
    Corner t;
    int i, turn;
    /* The corners as the game's integer pixels, which decide which way the quad is turned */
    c0.x = roundf(c0.x); c0.y = roundf(c0.y);
    c1.x = roundf(c1.x); c1.y = roundf(c1.y);
    c2.x = roundf(c2.x); c2.y = roundf(c2.y);
    c3.x = roundf(c3.x); c3.y = roundf(c3.y);
    turn = (int)((c1.x - c0.x) * (c2.y - c0.y) - (c1.y - c0.y) * (c2.x - c0.x));
    if (sink->count >= sink->max || turn == 0) return;
    if (turn < 0) {
        t = c0; c0 = c1; c1 = t;
        t = c2; c2 = c3; c3 = t;
    }
    q = &sink->out[sink->count++];
    corner[0] = &c0; corner[1] = &c1; corner[2] = &c2; corner[3] = &c3;
    for (i = 0; i < 4; i++) {
        q->x[i] = (short)corner[i]->x;
        q->y[i] = (short)corner[i]->y;
        q->r[i] = byte_of(corner[i]->r, sink->scale);
        q->g[i] = byte_of(corner[i]->g, sink->scale);
        q->b[i] = byte_of(corner[i]->b, sink->scale);
    }
}

/* A triangle: a quad with its last corner twice. */
static void triangle(Sink *sink, Corner a, Corner b, Corner c)
{
    quad(sink, a, b, c, c);
}

/* ---- glossy --------------------------------------------------------------- */

/* A faint rainbow over `rect`, a grid of corners coloured by where they are and by the time. */
static void rainbow_sheet(Sink *sink, const CardFoilRect *rect, int columns, int rows, float base, float hue_shift)
{
    Corner grid[(8 + 1) * (8 + 1)];
    int i, j;
    if (columns > 8) columns = 8;
    if (rows > 8) rows = 8;
    for (j = 0; j <= rows; j++) {
        for (i = 0; i <= columns; i++) {
            Corner *c = &grid[j * (columns + 1) + i];
            float u = (float)i / (float)columns, v = (float)j / (float)rows;
            float value = base * (0.7f + 0.3f * sinf(hue_shift * 6.2832f * 3.0f + u * 4.0f - v * 2.0f));
            c->x = (float)rect->x + u * (float)rect->w;
            c->y = (float)rect->y + v * (float)rect->h;
            rainbow(u * 0.7f + v * 0.5f + hue_shift, value, &c->r, &c->g, &c->b);
        }
    }
    for (j = 0; j < rows; j++) {
        for (i = 0; i < columns; i++) {
            quad(sink, grid[j * (columns + 1) + i], grid[j * (columns + 1) + i + 1],
                 grid[(j + 1) * (columns + 1) + i], grid[(j + 1) * (columns + 1) + i + 1]);
        }
    }
}

/* One arm of a glint on the edge of `rect`: from its top-left corner, arm 0 along the top and down the right
 * side, arm 1 down the left side and along the bottom, to the bottom-right corner. `head` is how far along
 * (0 to 1) its bright end is, and a tail of GLOSS_TAIL behind it fades out. The band is `thick` deep inside the edge. */
static void glint_arm(Sink *sink, const CardFoilRect *rect, int arm, float head, float thick, float peak)
{
    float width = (float)rect->w, height = (float)rect->h, total = width + height;
    float corner_at = (arm == 0 ? width : height) / total;
    float lo = head - GLOSS_TAIL, hi = head;
    float point[16];
    int n = 0, i;
    if (lo < 0) lo = 0;
    if (hi > 1) hi = 1;
    if (hi <= lo) return;
    for (i = 0; i <= 10; i++) point[n++] = lo + (hi - lo) * (float)i / 10.0f;
    if (corner_at > lo && corner_at < hi) {
        /* the corner is a point of its own, so that no piece bends round it */
        for (i = n; i > 0 && point[i - 1] > corner_at; i--) point[i] = point[i - 1];
        point[i] = corner_at;
        n++;
    }
    for (i = 0; i + 1 < n; i++) {
        float a = point[i], b = point[i + 1];
        float da = a * total, db = b * total, middle = (a + b) * 0.5f;
        int first_edge = middle < corner_at;
        Corner out0, out1, in0, in1;
        float ta = 1.0f - (head - a) / GLOSS_TAIL, tb = 1.0f - (head - b) / GLOSS_TAIL;
        float la, lb;
        float nx, ny;
        ta = ta < 0 ? 0 : ta;
        tb = tb < 0 ? 0 : tb;
        la = peak * ta * ta;
        lb = peak * tb * tb;
        if (arm == 0) {
            if (first_edge) {
                out0.x = (float)rect->x + da; out0.y = (float)rect->y;
                out1.x = (float)rect->x + db; out1.y = (float)rect->y;
                nx = 0; ny = 1;
            } else {
                out0.x = (float)(rect->x + rect->w); out0.y = (float)rect->y + (da - width);
                out1.x = (float)(rect->x + rect->w); out1.y = (float)rect->y + (db - width);
                nx = -1; ny = 0;
            }
        } else {
            if (first_edge) {
                out0.x = (float)rect->x; out0.y = (float)rect->y + da;
                out1.x = (float)rect->x; out1.y = (float)rect->y + db;
                nx = 1; ny = 0;
            } else {
                out0.x = (float)rect->x + (da - height); out0.y = (float)(rect->y + rect->h);
                out1.x = (float)rect->x + (db - height); out1.y = (float)(rect->y + rect->h);
                nx = 0; ny = -1;
            }
        }
        in0 = out0; in1 = out1;
        in0.x += nx * thick; in0.y += ny * thick;
        in1.x += nx * thick; in1.y += ny * thick;
        /* silver: a little cool, and the inside of the band dimmer than its edge */
        out0.r = la * 0.82f; out0.g = la * 0.88f; out0.b = la;
        out1.r = lb * 0.82f; out1.g = lb * 0.88f; out1.b = lb;
        in0.r = la * 0.25f; in0.g = la * 0.27f; in0.b = la * 0.3f;
        in1.r = lb * 0.25f; in1.g = lb * 0.27f; in1.b = lb * 0.3f;
        quad(sink, out0, out1, in0, in1);
    }
}

static void glossy(Sink *sink, const CardFoilRect *card, const CardFoilRect *art, unsigned ticks)
{
    unsigned phase = ticks % GLOSS_CYCLE;
    rainbow_sheet(sink, art, 6, 6, 58.0f, (float)(ticks % 1800) / 1800.0f);
    if (phase < GLOSS_SWEEP) {
        float head = (float)phase / (float)GLOSS_SWEEP * (1.0f + GLOSS_TAIL);
        int arm;
        for (arm = 0; arm < 2; arm++) {
            /* a soft wide glow under a narrow bright edge */
            glint_arm(sink, card, arm, head, 18.0f, 70.0f);
            glint_arm(sink, card, arm, head, 6.0f, 255.0f);
            glint_arm(sink, art, arm, head, 10.0f, 70.0f);
            glint_arm(sink, art, arm, head, 3.0f, 255.0f);
        }
    }
}

/* ---- royal ---------------------------------------------------------------- */

/* A rainbow turning about the middle of the card. */
static void turning_rainbow(Sink *sink, const CardFoilRect *card, unsigned ticks)
{
    enum { COLUMNS = 6, ROWS = 8 };
    Corner grid[(ROWS + 1) * (COLUMNS + 1)];
    float turn = (float)(ticks % 420) / 420.0f;
    int i, j;
    for (j = 0; j <= ROWS; j++) {
        for (i = 0; i <= COLUMNS; i++) {
            Corner *c = &grid[j * (COLUMNS + 1) + i];
            float u = (float)i / (float)COLUMNS - 0.5f, v = (float)j / (float)ROWS - 0.5f;
            float angle = atan2f(v * (float)card->h, u * (float)card->w) / 6.2832f;
            c->x = (float)card->x + (u + 0.5f) * (float)card->w;
            c->y = (float)card->y + (v + 0.5f) * (float)card->h;
            rainbow(angle + turn, 56.0f, &c->r, &c->g, &c->b);
        }
    }
    for (j = 0; j < ROWS; j++) {
        for (i = 0; i < COLUMNS; i++) {
            quad(sink, grid[j * (COLUMNS + 1) + i], grid[j * (COLUMNS + 1) + i + 1],
                 grid[(j + 1) * (COLUMNS + 1) + i], grid[(j + 1) * (COLUMNS + 1) + i + 1]);
        }
    }
}

/* Shards of glass over the card, lit in rainbow colours where a band running from the top-left to the
 * bottom-right is. The shards are a jittered grid cut in triangles; the same ones every time. */
static void shards(Sink *sink, const CardFoilRect *card, unsigned ticks)
{
    unsigned phase = ticks % ROYAL_CYCLE;
    float front, cell_w = (float)card->w / SHARD_COLUMNS, cell_h = (float)card->h / SHARD_ROWS;
    Corner grid[(SHARD_ROWS + 1)][(SHARD_COLUMNS + 1)];
    float shift = (float)(ticks % 600) / 600.0f;
    int i, j;
    if (phase >= ROYAL_SWEEP) return;
    front = -0.3f + (float)phase / (float)ROYAL_SWEEP * 1.6f;
    for (j = 0; j <= SHARD_ROWS; j++) {
        for (i = 0; i <= SHARD_COLUMNS; i++) {
            Corner *c = &grid[j][i];
            float x = (float)card->x + (float)i * cell_w, y = (float)card->y + (float)j * cell_h;
            if (i > 0 && i < SHARD_COLUMNS) x += (unit((unsigned)i, (unsigned)j, 1) - 0.5f) * cell_w * 0.8f;
            if (j > 0 && j < SHARD_ROWS) y += (unit((unsigned)i, (unsigned)j, 2) - 0.5f) * cell_h * 0.8f;
            c->x = x;
            c->y = y;
        }
    }
    for (j = 0; j < SHARD_ROWS; j++) {
        for (i = 0; i < SHARD_COLUMNS; i++) {
            int flip = (int)(hash((unsigned)i, (unsigned)j, 3) & 1), k;
            const Corner *tl = &grid[j][i], *tr = &grid[j][i + 1], *bl = &grid[j + 1][i], *br = &grid[j + 1][i + 1];
            const Corner *tri[2][3];
            if (flip) {
                tri[0][0] = tl; tri[0][1] = tr; tri[0][2] = bl;
                tri[1][0] = tr; tri[1][1] = br; tri[1][2] = bl;
            } else {
                tri[0][0] = tl; tri[0][1] = tr; tri[0][2] = br;
                tri[1][0] = tl; tri[1][1] = br; tri[1][2] = bl;
            }
            for (k = 0; k < 2; k++) {
                float cx = (tri[k][0]->x + tri[k][1]->x + tri[k][2]->x) / 3.0f;
                float cy = (tri[k][0]->y + tri[k][1]->y + tri[k][2]->y) / 3.0f;
                float along = ((cx - (float)card->x) / (float)card->w + (cy - (float)card->y) / (float)card->h) * 0.5f;
                float nearness = 1.0f - fabsf(along - front) / 0.24f;
                float light, bright = 0.55f + 0.45f * unit((unsigned)i, (unsigned)j, 10u + (unsigned)k);
                Corner c[3];
                int m;
                if (nearness <= 0.02f) continue;
                light = nearness * nearness * bright * 190.0f;
                for (m = 0; m < 3; m++) {
                    float hue = unit((unsigned)(tri[k][m]->x * 8.0f), (unsigned)(tri[k][m]->y * 8.0f), 7) + along * 1.4f + shift;
                    c[m].x = tri[k][m]->x;
                    c[m].y = tri[k][m]->y;
                    /* a hint of white in each colour: glass, not paint */
                    rainbow(hue, light * 0.8f, &c[m].r, &c[m].g, &c[m].b);
                    c[m].r += light * 0.2f;
                    c[m].g += light * 0.2f;
                    c[m].b += light * 0.2f;
                }
                triangle(sink, c[0], c[1], c[2]);
            }
        }
    }
}

int CardFoil_Quads(int finish, const CardFoilRect *card, const CardFoilRect *art, unsigned ticks, int fade,
                   CardFoilQuad *out, int max)
{
    Sink sink;
    sink.out = out;
    sink.count = 0;
    sink.max = max;
    sink.scale = fade < 0 ? 0 : fade > 128 ? 256 : fade * 2;
    if (!card || !art || card->w <= 0 || card->h <= 0 || art->w <= 0 || art->h <= 0) return 0;
    if (finish == CARD_FINISH_GLOSSY) {
        glossy(&sink, card, art, ticks);
    } else if (finish == CARD_FINISH_ROYAL) {
        turning_rainbow(&sink, card, ticks);
        shards(&sink, card, ticks);
    }
    return sink.count;
}
