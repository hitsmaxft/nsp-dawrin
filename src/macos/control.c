// Local-only interface for low-overhead input and GPU screenshot validation.
#include "hle.h"
#include <stdatomic.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include "controller.h"
extern _Atomic uint64_t native_package_reads, native_package_bytes;
extern _Atomic uint64_t native_shader_loads, native_shader_failures;
extern _Atomic uint64_t native_buttons, native_keyboard_buttons;
extern char *native_front_settings(const char *command);
extern _Atomic uint64_t native_touch_samples,native_touch_contacts;
extern uint64_t dm_nvn_frame_count(void);
extern uint64_t dm_audio_render_calls(void);
extern uint64_t dm_fs_commit_count(void);
extern void svc_thread_dump(void);
extern void dm_gfx_shot_at(long,const char *);
extern void native_touch(int,int,int);
static int server_fd;
static char socket_path[sizeof(((struct sockaddr_un *)0)->sun_path)];
static void cleanup_control(void) {unlink(socket_path);}
static void *control_loop(void *unused) {
    (void)unused;
    for(;;) {
        int fd=accept(server_fd,NULL,NULL);if(fd<0)continue;
        int no_sigpipe=1;setsockopt(fd,SOL_SOCKET,SO_NOSIGPIPE,&no_sigpipe,sizeof no_sigpipe);
        FILE *f=fdopen(fd,"r");if(!f){close(fd);continue;}
        char line[2048];
        if(fgets(line,sizeof line,f)) {
            line[strcspn(line,"\r\n")]=0;
            if(!strcmp(line,"settings") || !strncmp(line,"settings ",9)) {
                char *reply=native_front_settings(line[8] ? line+9 : "");
                dprintf(fd,"%s\n",reply);free(reply);
            } else if(!strncmp(line,"buttons ",8)) {
                char *end;uint64_t mask=strtoull(line+8,&end,0);
                if(*end)dprintf(fd,"{\"error\":\"invalid mask\"}\n");
                else {atomic_store(&native_buttons,mask);dprintf(fd,"{\"ok\":true}\n");}
            } else if(!strncmp(line,"touch ",6)) {
                int down,x,y;char extra;
                if(sscanf(line+6,"%d %d %d %c",&down,&x,&y,&extra)!=3||down<0||down>1||x<0||x>=1280||y<0||y>=720)
                    dprintf(fd,"{\"error\":\"touch requires down(0/1) x(0..1279) y(0..719)\"}\n");
                else {native_touch(down,x,y);dprintf(fd,"{\"ok\":true}\n");}
            } else if(!strncmp(line,"shot /",6)) {
                dm_gfx_shot_at(1,line+5);dprintf(fd,"{\"queued\":true}\n");
            } else if(!strcmp(line,"threads")) {
                svc_thread_dump();dprintf(fd,"{\"ok\":true,\"output\":\"runtime log\"}\n");
            } else if(!strcmp(line,"status")) {
                NativePad pad=native_controller_read();
                dprintf(fd,"{\"pid\":%d,\"frames\":%llu,\"buttons\":%llu,\"touch_samples\":%llu,\"touch_contacts\":%llu,\"controller_connected\":%u,\"controller_buttons\":%llu,\"sticks\":[%d,%d,%d,%d],\"package_reads\":%llu,\"package_bytes\":%llu,\"shader_loads\":%llu,\"shader_failures\":%llu,\"audio_callbacks\":%llu,\"save_commits\":%llu}\n",getpid(),dm_nvn_frame_count(),(atomic_load(&native_buttons)|atomic_load(&native_keyboard_buttons)),atomic_load(&native_touch_samples),atomic_load(&native_touch_contacts),pad.connected,pad.buttons,pad.lx,pad.ly,pad.rx,pad.ry,atomic_load(&native_package_reads),atomic_load(&native_package_bytes),atomic_load(&native_shader_loads),atomic_load(&native_shader_failures),dm_audio_render_calls(),dm_fs_commit_count());
            } else dprintf(fd,"{\"error\":\"expected status, buttons MASK, or shot /PATH\"}\n");
        }
        fclose(f);
    }
    return NULL;
}
void native_control_start(void) {
    const char *path=getenv("DM_CONTROL");if(!path||!*path)return;
    if(strlen(path)>=sizeof socket_path)die("DM_CONTROL path too long");
    struct sockaddr_un addr={.sun_family=AF_UNIX};strlcpy(addr.sun_path,path,sizeof addr.sun_path);
    server_fd=socket(AF_UNIX,SOCK_STREAM,0);if(server_fd<0)die("control socket");
    if(!access(path,F_OK)) {
        if(!connect(server_fd,(struct sockaddr *)&addr,sizeof addr))die("Another native runner owns %s",path);
        if(errno!=ECONNREFUSED)die("Cannot inspect control socket %s",path);
        struct stat st;if(lstat(path,&st)||!S_ISSOCK(st.st_mode)||st.st_uid!=getuid())die("Unsafe stale control path");
        unlink(path);
    }
    if(bind(server_fd,(struct sockaddr *)&addr,sizeof addr)||chmod(path,0600)||listen(server_fd,4))die("Cannot bind control socket");
    strlcpy(socket_path,path,sizeof socket_path);atexit(cleanup_control);
    pthread_t thread;if(pthread_create(&thread,NULL,control_loop,NULL))die("control thread");pthread_detach(thread);
    LOG("macOS control socket: %s",path);
}
