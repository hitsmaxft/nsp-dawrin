// Independent report UI: it remains available after the native runtime exits.
#import <Cocoa/Cocoa.h>

static BOOL valid_report(NSDictionary *report) {
    if (![report isKindOfClass:NSDictionary.class]) return NO;
    for (NSString *key in @[@"title",@"issue_body",@"agent_prompt",@"issue_url"])
        if (![report[key] isKindOfClass:NSString.class] || [report[key] length]>65536) return NO;
    if (![report[@"body_in_url"] isKindOfClass:NSNumber.class]) return NO;
    NSURLComponents *url=[NSURLComponents componentsWithString:report[@"issue_url"]];
    NSArray *parts=[url.path componentsSeparatedByString:@"/"];
    return [url.scheme isEqual:@"https"] && [url.host isEqual:@"github.com"] && !url.user && !url.password && !url.port &&
        parts.count==5 && [parts[3] isEqual:@"issues"] && [parts[4] isEqual:@"new"];
}
@interface CrashReportController : NSObject <NSApplicationDelegate,NSWindowDelegate>
@property NSDictionary *report;
@property NSURL *reportURL;
@property NSWindow *window;
@property NSTextView *preview;
@property NSSegmentedControl *tabs;
@property NSTextField *status;
- (instancetype)initWithReport:(NSDictionary *)report URL:(NSURL *)url;
- (void)selectPreview:(id)sender;
@end
@implementation CrashReportController
- (instancetype)initWithReport:(NSDictionary *)report URL:(NSURL *)url {
    if (!(self=[super init])) return nil;
    self.report=report;self.reportURL=url;
    self.window=[[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,860,650)
        styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskResizable
        backing:NSBackingStoreBuffered defer:NO];
    self.window.title=@"nsp-dawrin — Crash Report";self.window.delegate=self;self.window.releasedWhenClosed=NO;
    self.window.minSize=NSMakeSize(820,540);
    NSView *view=self.window.contentView;
    NSTextField *heading=[NSTextField labelWithString:@"The runtime exited unexpectedly"];
    heading.frame=NSMakeRect(24,603,810,28);heading.font=[NSFont boldSystemFontOfSize:20];
    heading.autoresizingMask=NSViewMinYMargin|NSViewWidthSizable;[view addSubview:heading];
    self.tabs=[NSSegmentedControl segmentedControlWithLabels:@[@"GitHub Issue",@"Agent Prompt"] trackingMode:NSSegmentSwitchTrackingSelectOne
        target:self action:@selector(selectPreview:)];
    self.tabs.selectedSegment=0;self.tabs.frame=NSMakeRect(24,565,370,28);self.tabs.autoresizingMask=NSViewMinYMargin;
    [view addSubview:self.tabs];
    NSScrollView *scroll=[[NSScrollView alloc] initWithFrame:NSMakeRect(24,100,812,450)];
    scroll.hasVerticalScroller=YES;scroll.borderType=NSBezelBorder;scroll.autoresizingMask=NSViewWidthSizable|NSViewHeightSizable;
    self.preview=[[NSTextView alloc] initWithFrame:scroll.bounds];self.preview.editable=NO;self.preview.selectable=YES;
    self.preview.font=[NSFont monospacedSystemFontOfSize:12 weight:NSFontWeightRegular];
    self.preview.autoresizingMask=NSViewWidthSizable;self.preview.verticallyResizable=YES;self.preview.horizontallyResizable=NO;
    self.preview.textContainer.containerSize=NSMakeSize(scroll.contentSize.width,CGFLOAT_MAX);
    self.preview.textContainer.widthTracksTextView=YES;scroll.documentView=self.preview;[view addSubview:scroll];
    NSArray *titles=@[@"Open GitHub Draft",@"Copy Agent Prompt",@"Copy Issue",@"Show Files",@"Close"];
    SEL actions[]={@selector(openIssue:),@selector(copyPrompt:),@selector(copyIssue:),@selector(showFiles:),@selector(close:)};
    CGFloat x=24;
    for (NSUInteger i=0;i<titles.count;i++) {
        CGFloat width=i<2 ? 180 : 135;
        NSButton *button=[NSButton buttonWithTitle:titles[i] target:self action:actions[i]];
        button.frame=NSMakeRect(x,55,width,32);x+=width+7;[view addSubview:button];
    }
    self.status=[NSTextField labelWithString:@"Preview the report, then finish submission in your browser. Raw logs stay in Show Files."];
    self.status.frame=NSMakeRect(24,17,810,30);self.status.autoresizingMask=NSViewWidthSizable;
    self.status.font=[NSFont systemFontOfSize:11];self.status.maximumNumberOfLines=2;[view addSubview:self.status];
    [self selectPreview:nil];return self;
}
- (void)selectPreview:(id)sender {
    self.preview.string=self.report[self.tabs.selectedSegment==0 ? @"issue_body":@"agent_prompt"];
    [self.preview scrollRangeToVisible:NSMakeRange(0,0)];
}
- (void)copy:(NSString *)text {
    NSPasteboard *pasteboard=NSPasteboard.generalPasteboard;[pasteboard clearContents];
    if (![pasteboard setString:text forType:NSPasteboardTypeString]) self.status.stringValue=@"Clipboard unavailable";
    else self.status.stringValue=@"Copied to clipboard";
}
- (void)copyPrompt:(id)sender { [self copy:self.report[@"agent_prompt"]]; }
- (void)copyIssue:(id)sender { [self copy:self.report[@"issue_body"]]; }
- (void)openIssue:(id)sender {
    if (![self.report[@"body_in_url"] boolValue]) {
        [self copy:self.report[@"issue_body"]];self.status.stringValue=@"Issue text copied. Paste it into the browser draft before submitting.";
    }
    if (![NSWorkspace.sharedWorkspace openURL:[NSURL URLWithString:self.report[@"issue_url"]]])
        self.status.stringValue=@"Could not open the browser. Copy the issue text and open the repository manually.";
}
- (void)showFiles:(id)sender { [NSWorkspace.sharedWorkspace activateFileViewerSelectingURLs:@[self.reportURL]]; }
- (void)close:(id)sender { [NSApp terminate:nil]; }
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)app { return YES; }
@end

int main(int argc,const char **argv) {
    @autoreleasepool {
        if (argc<2) { fprintf(stderr,"usage: crash-report REPORT.json [--validate | --check-ui]\n");return 2; }
        NSURL *url=[NSURL fileURLWithPath:@(argv[1])];
        NSData *data=[NSData dataWithContentsOfURL:url];
        if (!data || data.length>256*1024) { fprintf(stderr,"Report missing or too large\n");return 2; }
        NSDictionary *report=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
        if (!valid_report(report)) { fprintf(stderr,"Invalid crash report\n");return 2; }
        if (argc>2 && !strcmp(argv[2],"--validate")) { puts("PASS: report fields and GitHub destination");return 0; }
        [NSApplication sharedApplication];[NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
        CrashReportController *controller=[[CrashReportController alloc] initWithReport:report URL:url];
        NSApp.delegate=controller;
        NSMenu *menu=[NSMenu new];NSMenuItem *app=[[NSMenuItem alloc] initWithTitle:@"Crash Report" action:NULL keyEquivalent:@""];
        [menu addItem:app];app.submenu=[[NSMenu alloc] initWithTitle:@"Crash Report"];
        NSMenuItem *quit=[[NSMenuItem alloc] initWithTitle:@"Close Report" action:@selector(terminate:) keyEquivalent:@"q"];
        quit.target=NSApp;[app.submenu addItem:quit];NSApp.mainMenu=menu;
        if (argc>2 && !strcmp(argv[2],"--check-ui")) {
            NSCAssert([controller.preview.string isEqual:report[@"issue_body"]],@"Issue preview differs");
            controller.tabs.selectedSegment=1;[controller selectPreview:nil];
            NSCAssert([controller.preview.string isEqual:report[@"agent_prompt"]],@"Agent prompt differs");
            NSUInteger buttons=0;
            for (NSView *view in controller.window.contentView.subviews)
                if ([view isKindOfClass:NSButton.class]) buttons++;
            NSCAssert(buttons==5,@"Missing report actions");
            puts("PASS: issue preview, agent prompt preview and five user actions; no browser or clipboard action executed");return 0;
        }
        [controller.window center];[controller.window makeKeyAndOrderFront:nil];[NSApp activate];[NSApp run];
    }
    return 0;
}
