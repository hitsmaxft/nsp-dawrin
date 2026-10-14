// Runtime facts are derived from bound resources, independent of engine assets.
// Included after replay state and texture registration declarations.
static NSString *runtime_scalar(uint32_t pixel) {
    switch(pixel) {
        case 13:case 23:case 33:case 53:case 63:case 73:case 91:case 103:case 113:case 123:return @"uint";
        case 14:case 24:case 34:case 54:case 64:case 74:case 104:case 114:case 124:return @"sint";
        default:return @"float";
    }
}
static NSString *runtime_image_format(uint32_t pixel) {
    switch(pixel) {
        case 10:return @"R8Unorm";case 13:return @"R8Uint";case 14:return @"R8Sint";
        case 23:return @"R16Uint";case 24:return @"R16Sint";case 25:return @"R16Float";
        case 30:return @"R8G8Unorm";case 33:return @"R8G8Uint";case 34:return @"R8G8Sint";
        case 53:return @"R32Uint";case 54:return @"R32Sint";case 55:return @"R32Float";
        case 63:return @"R16G16Uint";case 64:return @"R16G16Sint";case 65:return @"R16G16Float";
        case 70:return @"R8G8B8A8Unorm";case 73:return @"R8G8B8A8Uint";case 74:return @"R8G8B8A8Sint";
        case 103:return @"R32G32Uint";case 104:return @"R32G32Sint";case 105:return @"R32G32Float";
        case 113:return @"R16G16B16A16Uint";case 114:return @"R16G16B16A16Sint";case 115:return @"R16G16B16A16Float";
        case 123:return @"R32G32B32A32Uint";case 124:return @"R32G32B32A32Sint";case 125:return @"R32G32B32A32Float";
        default:return nil;
    }
}
static NSDictionary *runtime_shader_facts(const NVNshaderData *shader) {
    uint32_t header;memcpy(&header,(void *)(uintptr_t)(shader->data+0x30),4);
    int kind=(header>>10)&15;int stage=kind==1?0:kind==5?1:-1;
    if(S.stage_prog[5])for(unsigned i=0;i<S.stage_prog[5]->nstage;i++)
        if(S.stage_prog[5]->sd[i].control==shader->control)stage=5;
    if(stage<0)MDIE("Unsupported runtime shader stage: %d",kind);
    NSMutableDictionary *textures=[NSMutableDictionary new],*images=[NSMutableDictionary new];
    static NSString *targets[]={@"1d",@"2d",@"3d",@"1darray",@"2darray",@"2dms",@"2dmsarray",@"2d",@"cube",@"cubearray",@"buffer"};
    pthread_mutex_lock(&g_rmu);
    for(int category=0;category<2;category++)for(int slot=0;slot<(category?32:128);slot++) {
        uint64_t handle=category?S.img[stage][slot]:S.tex[stage][slot];int id_=(int)(handle&0xfffff);
        if(!id_ || id_>=g_ntreg || !g_treg[id_].ok)continue;
        treg_t *record=&g_treg[id_];int target=record->has_v && record->v.set_target?record->v.target:record->t.d.target;
        int format=record->has_v && record->v.set_format?record->v.format:record->t.d.format;
        if(target<0 || target>10)continue;
        NSString *index=[NSString stringWithFormat:@"%d",slot];
        if(!category)textures[index]=targets[target];
        else {
            uint32_t pixel;uint8_t swizzle[4];
            NSString *name=nvn_fmt_to_mtl(format,&pixel,swizzle)?runtime_image_format(pixel):nil;
            if(name)images[index]=@{@"type":targets[target],@"fmt":name};
        }
    }
    pthread_mutex_unlock(&g_rmu);
    NSMutableDictionary *attributes=[NSMutableDictionary new],*outputs=[NSMutableDictionary new];
    if(stage==0)for(int i=0;i<S.nattr && i<16;i++) {
        uint32_t pixel;uint8_t swizzle[4];
        if(nvn_fmt_to_mtl(S.attr[i].fmt,&pixel,swizzle))attributes[[NSString stringWithFormat:@"%d",i]]=runtime_scalar(pixel);
    }
    if(stage==1 && R.has_rt)for(int i=0;i<R.rt.n && i<8;i++)if(R.rt.color[i]) {
        int format=R.rt.has_cview[i] && R.rt.cview[i].set_format?R.rt.cview[i].format:R.rt.color[i]->d.format;
        uint32_t pixel;uint8_t swizzle[4];
        if(nvn_fmt_to_mtl(format,&pixel,swizzle))outputs[[NSString stringWithFormat:@"%d",i]]=runtime_scalar(pixel);
    }
    return @{@"stage":stage==0?@"vs":stage==1?@"ps":@"cs",@"values":@{@"tex":textures,@"img":images,@"attr":attributes,@"fout":outputs}};
}
