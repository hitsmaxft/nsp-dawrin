#import "settings_ui.h"
#import "settings.h"
#import "controller.h"

@interface SettingsController : NSWindowController <NSWindowDelegate>
@property NSPopUpButton *mode;
@property NSPopUpButton *resolution;
@property NSPopUpButton *controller;
@property NSButton *fullscreen;
@property NSTextField *status;
@property NSMutableArray<NSButton *> *bindingButtons;
@property NSInteger recording;
@property id keyMonitor;
- (void)refresh;
@end

static NSTextField *label(NSString *text, NSRect frame) {
    NSTextField *view=[NSTextField labelWithString:text];view.frame=frame;return view;
}
static NSPopUpButton *popup(NSView *view, NSRect frame, NSArray *items, id target, SEL action) {
    NSPopUpButton *button=[[NSPopUpButton alloc] initWithFrame:frame pullsDown:NO];
    [button addItemsWithTitles:items];button.target=target;button.action=action;[view addSubview:button];return button;
}
@implementation SettingsController
- (instancetype)init {
    NSWindow *window=[[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,720,650)
        styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable backing:NSBackingStoreBuffered defer:NO];
    if (!(self=[super initWithWindow:window])) return nil;
    self.recording=-1;window.title=@"Settings";window.delegate=self;window.releasedWhenClosed=NO;
    window.collectionBehavior=NSWindowCollectionBehaviorFullScreenAuxiliary|NSWindowCollectionBehaviorMoveToActiveSpace;
    NSView *view=window.contentView;
    [view addSubview:label(@"Display",NSMakeRect(24,610,200,24))];
    self.fullscreen=[NSButton checkboxWithTitle:@"Full screen" target:self action:@selector(changeFullscreen:)];
    self.fullscreen.frame=NSMakeRect(430,610,250,24);[view addSubview:self.fullscreen];
    [view addSubview:label(@"System mode",NSMakeRect(24,573,140,24))];
    self.mode=popup(view,NSMakeRect(170,570,280,28),@[@"Handheld — 720p",@"Console — 1080p"],self,@selector(changeMode:));
    [view addSubview:label(@"Applies when you next launch a game.",NSMakeRect(170,546,450,20))];
    [view addSubview:label(@"Display output",NSMakeRect(24,510,140,24))];
    self.resolution=popup(view,NSMakeRect(170,507,280,28),@[@"Automatic (window / display)",@"1280 × 720",@"1920 × 1080"],self,@selector(changeResolution:));
    [view addSubview:label(@"Scales the presented image; the game chooses its render resolution.",NSMakeRect(170,483,530,20))];
    [view addSubview:label(@"Controller",NSMakeRect(24,445,140,24))];
    self.controller=popup(view,NSMakeRect(170,442,510,28),@[],self,@selector(changeController:));
    [view addSubview:label(@"Keyboard bindings",NSMakeRect(24,400,250,24))];
    [view addSubview:label(@"Click a binding, then press a key. Assigning a used key moves it here.",NSMakeRect(24,376,660,20))];
    self.bindingButtons=[NSMutableArray array];
    NSArray *names=native_binding_names();
    for (NSInteger i=0;i<24;i++) {
        CGFloat x=24+(i/12)*348,y=344-(i%12)*25;
        [view addSubview:label(names[i],NSMakeRect(x,y,150,22))];
        NSButton *button=[NSButton buttonWithTitle:@"" target:self action:@selector(recordKey:)];
        button.frame=NSMakeRect(x+152,y-2,116,26);button.tag=i;
        button.accessibilityLabel=[@"Bind " stringByAppendingString:names[i]];
        [view addSubview:button];[self.bindingButtons addObject:button];
        NSButton *clear=[NSButton buttonWithTitle:@"Clear" target:self action:@selector(clearKey:)];
        clear.frame=NSMakeRect(x+270,y-2,56,26);clear.tag=i;[view addSubview:clear];
    }
    NSButton *reset=[NSButton buttonWithTitle:@"Reset Keyboard" target:self action:@selector(resetKeys:)];
    reset.frame=NSMakeRect(24,28,150,30);[view addSubview:reset];
    NSButton *cancel=[NSButton buttonWithTitle:@"Cancel Recording" target:self action:@selector(cancelRecording:)];
    cancel.frame=NSMakeRect(180,28,160,30);[view addSubview:cancel];
    self.status=label(@"",NSMakeRect(24,5,675,20));self.status.font=[NSFont systemFontOfSize:11];[view addSubview:self.status];
    [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(refresh) name:NativeSettingsChanged object:nil];
    [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(refresh) name:NativeControllersChanged object:nil];
    __weak SettingsController *weakSelf=self;
    self.keyMonitor=[NSEvent addLocalMonitorForEventsMatchingMask:(NSEventMaskKeyDown|NSEventMaskFlagsChanged) handler:^NSEvent *(NSEvent *event) {
        SettingsController *strong=weakSelf;
        if (!strong || strong.recording<0 || event.window!=strong.window) return event;
        if (event.modifierFlags & NSEventModifierFlagCommand) return event;
        if (event.type==NSEventTypeFlagsChanged) {
            if (!(event.modifierFlags & native_key_modifier(event.keyCode))) return event;
        } else if (event.isARepeat) return nil;
        if (event.keyCode>127) return nil;
        [strong bindKey:event.keyCode];return nil;
    }];
    [self refresh];return self;
}
- (void)save:(NSDictionary *)patch {
    NSError *error=nil;
    if (!native_settings_update(patch,&error)) self.status.stringValue=error.localizedDescription ?: @"Could not save settings";
    else self.status.stringValue=@"Settings saved";
    [self refresh];
}
- (void)refresh {
    NSDictionary *data=native_settings_snapshot();
    [self.mode selectItemAtIndex:[data[@"mode"] isEqual:@"console"]];
    [self.resolution selectItemAtIndex:[@[@0,@720,@1080] indexOfObject:data[@"resolution"]]];
    self.fullscreen.state=[data[@"fullscreen"] boolValue];
    [self.controller removeAllItems];
    [self.controller addItemsWithTitles:@[@"Automatic",@"Keyboard only"]];
    self.controller.itemArray[0].representedObject=@"auto";self.controller.itemArray[1].representedObject=@"none";
    for (NSDictionary *device in native_controller_devices()) {
        [self.controller addItemWithTitle:device[@"name"]];self.controller.lastItem.representedObject=device[@"id"];
    }
    NSString *selection=native_controller_selection();
    if ([selection isEqual:@"unavailable"]) {
        [self.controller addItemWithTitle:@"Preferred controller disconnected"];
        self.controller.lastItem.representedObject=@"unavailable";self.controller.lastItem.enabled=NO;
    }
    for (NSMenuItem *item in self.controller.itemArray) if ([item.representedObject isEqual:selection]) [self.controller selectItem:item];
    for (NSInteger i=0;i<24;i++) {
        NSMutableArray *keys=[NSMutableArray array];
        for (NSNumber *key in data[@"bindings"][[NSString stringWithFormat:@"%ld",(long)i]]) [keys addObject:native_key_label(key.unsignedShortValue)];
        self.bindingButtons[i].title=i==self.recording ? @"Press a key…" : (keys.count ? [keys componentsJoinedByString:@" / "] : @"Unbound");
    }
}
- (void)changeMode:(id)sender { [self save:@{@"mode":self.mode.indexOfSelectedItem ? @"console":@"handheld"}]; }
- (void)changeResolution:(id)sender { [self save:@{@"resolution":@[@0,@720,@1080][self.resolution.indexOfSelectedItem]}]; }
- (void)changeFullscreen:(id)sender { [self save:@{@"fullscreen":@(self.fullscreen.state==NSControlStateValueOn)}]; }
- (void)changeController:(id)sender {
    NSError *error=nil;
    if (!native_controller_choose(self.controller.selectedItem.representedObject,&error)) self.status.stringValue=error.localizedDescription;
    else self.status.stringValue=@"Controller selection saved";
    [self refresh];
}
- (void)recordKey:(NSButton *)sender { self.recording=sender.tag;[self refresh]; }
- (void)cancelRecording:(id)sender { self.recording=-1;[self refresh]; }
- (void)bindKey:(unsigned short)key {
    NSMutableDictionary *bindings=[native_settings_snapshot()[@"bindings"] mutableCopy];
    for (NSString *action in bindings.allKeys) {
        NSMutableArray *keys=[bindings[action] mutableCopy];[keys removeObject:@(key)];bindings[action]=keys;
    }
    bindings[[NSString stringWithFormat:@"%ld",(long)self.recording]]=@[@(key)];
    self.recording=-1;[self save:@{@"bindings":bindings}];
}
- (void)clearKey:(NSButton *)sender {
    self.recording=-1;NSMutableDictionary *bindings=[native_settings_snapshot()[@"bindings"] mutableCopy];
    [bindings removeObjectForKey:[NSString stringWithFormat:@"%ld",(long)sender.tag]];[self save:@{@"bindings":bindings}];
}
- (void)resetKeys:(id)sender {
    self.recording=-1;
    [self save:@{@"bindings":@{@"0":@[@6,@49],@"1":@[@7,@53],@"2":@[@0],@"3":@[@1],@"10":@[@36],
        @"12":@[@123],@"13":@[@126],@"14":@[@124],@"15":@[@125]}}];
}
- (void)windowWillClose:(NSNotification *)notification { self.recording=-1;[self refresh]; }
- (void)windowDidResignKey:(NSNotification *)notification { self.recording=-1;[self refresh]; }
@end
void native_settings_show(NSWindow *parent) {
    static SettingsController *controller;
    if (!controller) controller=[SettingsController new];
    [controller refresh];[controller.window center];[controller showWindow:nil];[controller.window makeKeyAndOrderFront:nil];
}
