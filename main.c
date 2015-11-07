#include <stdio.h>
#include <stdlib.h>
//#include <nmmintrin.h>
#include <math.h>

#include <libavutil/imgutils.h>
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libswscale/swscale.h>

static AVFormatContext *fmt_ctx = NULL;
static AVCodecContext *video_dec_ctx = NULL;
static int src_width, src_height;
static enum AVPixelFormat src_pix_fmt;
static int dst_width = 8, dst_height = 8;
static enum AVPixelFormat dst_pix_fmt = AV_PIX_FMT_GRAY8;
static AVStream *video_stream = NULL;
static const char *src_filename = NULL;
static const char *video_dst_filename = NULL;
static FILE *video_dst_file = NULL;
static struct SwsContext *sws_ctx;

static uint8_t *video_dst_data[4] = {NULL};
static int video_dst_linesize[4];
static int video_dst_bufsize;

static int video_stream_idx = -1;
static AVFrame *frame = NULL;
static AVPacket pkt;
static int video_frame_count = 0;

static int refcount = 0;

//static int hamming_distance(char *a, char *b)
//{
//    uint64_t a_value, b_value;
//    a_value = strtoul(a, NULL, 16);
//    b_value = strtoul(b, NULL, 16);
//    
//    int ret = (int)_mm_popcnt_u64(a_value ^ b_value);
//    return ret;
//}

static void average_hash(char *hash, int* len)
{
    uint16_t sum = 0;
    int gray_size = dst_width * dst_height;
    uint8_t *gray_data = video_dst_data[0];
    for (int i = 0; i < gray_size; i++) {
        sum += gray_data[i];
    }

    uint8_t avg = sum / gray_size;
    *len = gray_size / 4;
    for (int i = 0, j = 0; i < gray_size; i += 4, j++) {
        uint8_t value =
        (gray_data[i] > avg) * 8 +
        (gray_data[i+1] > avg) * 4 +
        (gray_data[i+2] > avg) * 2 +
        (gray_data[i+3] > avg);
        
        char c[2];
        sprintf(c, "%x", value);
        strcat(hash, c);
    }
}

static int decode_packet(int *got_frame, int cached)
{
    int len = 0;
    int decoded = pkt.size;
    
    *got_frame = 0;
    
    if (pkt.stream_index == video_stream_idx) {
        /* decode video frame */
        len = avcodec_decode_video2(video_dec_ctx, frame, got_frame, &pkt);
        if (len < 0) {
            fprintf(stderr, "Error decoding video frame (%s)\n", av_err2str(len));
            return len;
        }
        
        if (*got_frame) {
            if (frame->width != src_width || frame->height != src_height ||
                frame->format != src_pix_fmt) {
                /* To handle this change, one could call av_image_alloc again and
                 * decode the following frames into another rawvideo file. */
                fprintf(stderr, "Error: Width, height and pixel format have to be "
                        "constant in a rawvideo file, but the width, height or "
                        "pixel format of the input video changed:\n"
                        "old: width = %d, height = %d, format = %s\n"
                        "new: width = %d, height = %d, format = %s\n",
                        src_width, src_height, av_get_pix_fmt_name(src_pix_fmt),
                        frame->width, frame->height,
                        av_get_pix_fmt_name(frame->format));
                return -1;
            }
            
            video_frame_count++;
            //printf("video_frame%s n:%d coded_n:%d pts:%s\n",
            //       cached ? "(cached)" : "",
            //       video_frame_count, frame->coded_picture_number,
            //       av_ts2timestr(frame->pts, &video_dec_ctx->time_base));
            
            /* convert to RGB */
            sws_scale(sws_ctx,
                      (const uint8_t * const*)frame->data, frame->linesize, 0, src_height,
                      video_dst_data, video_dst_linesize);

            /* write to rawvideo file */
            //fwrite(video_dst_data[0], 1, video_dst_bufsize, video_dst_file);
        }
    }
    
    /* If we use frame reference counting, we own the data and need
     * to de-reference it when we don't use it anymore */
    if (*got_frame && refcount)
        av_frame_unref(frame);
    
    return decoded;
}

static int open_codec_context(int *stream_idx, AVFormatContext *fmt_ctx, enum AVMediaType type)
{
    int ret, stream_index;
    AVStream *st;
    AVCodecContext *dec_ctx = NULL;
    AVCodec *dec = NULL;
    AVDictionary *opts = NULL;
    
    ret = av_find_best_stream(fmt_ctx, type, -1, -1, NULL, 0);
    if (ret < 0) {
        fprintf(stderr, "Could not find %s stream in input file '%s'\n",
                av_get_media_type_string(type), src_filename);
        return ret;
    }
    else {
        stream_index = ret;
        st = fmt_ctx->streams[stream_index];
        
        /* find decoder for the stream */
        dec_ctx = st->codec;
        dec = avcodec_find_decoder(dec_ctx->codec_id);
        if (!dec) {
            fprintf(stderr, "Failed to find %s codec\n",
                    av_get_media_type_string(type));
            return AVERROR(EINVAL);
        }
        
        /* Init the decoders, with or without reference counting */
        av_dict_set(&opts, "refcounted_frames", refcount ? "1" : "0", 0);
        if ((ret = avcodec_open2(dec_ctx, dec, &opts)) < 0) {
            fprintf(stderr, "Failed to open %s codec\n",
                    av_get_media_type_string(type));
            return ret;
        }
        *stream_idx = stream_index;
    }
    
    return 0;
}

int main(int argc, const char * argv[])
{
    int ret = 0, got_frame;
    int err;
    
    if (argc < 3) {
        printf("usage: %s src dst\n", argv[0]);
        return 1;
    }
    src_filename = argv[1];
    video_dst_filename = argv[2];
    
    avformat_network_init();
    
    /* register all formats and codecs */
    av_register_all();
    
    /* open input file, and allocate format context */
    err = avformat_open_input(&fmt_ctx, src_filename, NULL, NULL);
    if (err < 0) {
        fprintf(stderr, "Could not open source file %s\n", src_filename);
        return 1;
    }
    
    /* retrieve stream information */
    err = avformat_find_stream_info(fmt_ctx, NULL);
    if (err < 0) {
        fprintf(stderr, "Could not find stream information\n");
        return 1;
    }
    
    if (open_codec_context(&video_stream_idx, fmt_ctx, AVMEDIA_TYPE_VIDEO) >= 0) {
        video_stream = fmt_ctx->streams[video_stream_idx];
        video_dec_ctx = video_stream->codec;
        
        video_dst_file = fopen(video_dst_filename, "wb");
        if (!video_dst_file) {
            fprintf(stderr, "Could not open destination file %s\n", video_dst_filename);
            ret = 1;
            goto end;
        }
        
        /* allocate image where the decoded image will be put */
        src_width = video_dec_ctx->width;
        src_height = video_dec_ctx->height;
        src_pix_fmt = video_dec_ctx->pix_fmt;
    }
    
    /* dump input information to stderr */
    av_dump_format(fmt_ctx, 0, src_filename, 0);
    
    if (!video_stream) {
        fprintf(stderr, "Could not find video stream in the input, aborting\n");
        ret = 1;
        goto end;
    }
    
    /* create scaling context */
    sws_ctx = sws_getContext(src_width, src_height, src_pix_fmt,
                             dst_width, dst_height, dst_pix_fmt,
                             SWS_BICUBIC, NULL, NULL, NULL);
    if (!sws_ctx) {
        fprintf(stderr,
                "Impossible to create scale context for the conversion "
                "fmt:%s s:%dx%d -> fmt:%s s:%dx%d\n",
                av_get_pix_fmt_name(src_pix_fmt), src_width, src_height,
                av_get_pix_fmt_name(dst_pix_fmt), dst_width, dst_height);
        ret = AVERROR(EINVAL);
        goto end;
    }

    ret = av_image_alloc(video_dst_data, video_dst_linesize,
                         dst_width, dst_height, dst_pix_fmt, 1);
    if (ret < 0) {
        fprintf(stderr, "Could not allocate raw video buffer\n");
        goto end;
    }
    video_dst_bufsize = ret;
    
    frame = av_frame_alloc();
    if (!frame) {
        fprintf(stderr, "Could not allocate frame\n");
        ret = AVERROR(ENOMEM);
        goto end;
    }
    
    /* initialize packet, set data to NULL, let the demuxer fill it */
    av_init_packet(&pkt);
    pkt.data = NULL;
    pkt.size = 0;
    
    if (video_stream)
        printf("Demuxing video from file '%s' into '%s'\n", src_filename, video_dst_filename);
    
    /* read frames from the file */
    int8_t step = 2;
    int64_t timestamp = 0;
    while (timestamp * video_stream->time_base.den < video_stream->duration &&
           av_read_frame(fmt_ctx, &pkt) >= 0) {
        AVPacket orig_pkt = pkt;
        do {
            ret = decode_packet(&got_frame, 0);
            if (ret < 0)
                break;
            pkt.data += ret;
            pkt.size -= ret;
        } while (pkt.size > 0);
        av_packet_unref(&orig_pkt);

        if (got_frame) {
            /* calculate hash */
            int hash_len;
            char hash[video_dst_bufsize];
            memset(hash, 0, sizeof(hash));
            average_hash(hash, &hash_len);
            
            /* write to output */
            fwrite(hash, sizeof(char), sizeof(char) * hash_len, video_dst_file);
            fwrite("\n", sizeof(char), sizeof(char), video_dst_file);
            
            timestamp += step;
            avformat_seek_file(fmt_ctx, video_stream_idx, 0, timestamp * video_stream->time_base.den, timestamp * video_stream->time_base.den, AVSEEK_FLAG_FRAME);
            //avcodec_flush_buffers(video_dec_ctx);
        }
    }
    
    printf("Demuxing succeeded.\n");
    
end:
    avcodec_close(video_dec_ctx);
    avformat_close_input(&fmt_ctx);
    if (video_dst_file)
        fclose(video_dst_file);
    av_frame_free(&frame);
    av_free(video_dst_data[0]);
    sws_freeContext(sws_ctx);
    
    return ret < 0;
}
