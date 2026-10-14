#include "../src/host/hle_font.c"
#import <CoreText/CoreText.h>
#include <assert.h>
int main(void){
    assert(font_state(-1)==0&&font_address(6)==NULL&&!font_size(6));
    font_load(0);const void *data=font_address(0);size_t size=font_size(0);
    assert(data&&size>12&&font_state(0)==1&&font_address(1)==data);
    CGDataProviderRef provider=CGDataProviderCreateWithData(NULL,data,size,NULL);
    CGFontRef cgfont=CGFontCreateWithDataProvider(provider);assert(cgfont);
    CTFontRef font=CTFontCreateWithGraphicsFont(cgfont,12,NULL,NULL);assert(font);
    UniChar text[]={0x41,0x4e2d,0x6587};CGGlyph glyphs[3];
    assert(CTFontGetGlyphsForCharacters(font,text,glyphs,3));
    CFRelease(font);CGFontRelease(cgfont);CGDataProviderRelease(provider);
    puts("PASS: installed font loading, stable byte view, valid font data and Latin/CJK glyphs");
}
