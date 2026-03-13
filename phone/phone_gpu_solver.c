/* Erdos-Straus OpenCL solver for Adreno 610 (phone GPU)
 * Self-contained — no OpenCL headers needed, defines everything inline.
 * Compile: clang -O2 -o phone_gpu phone_gpu_solver.c -L/vendor/lib64 -lOpenCL
 * Usage:   ./phone_gpu phone_chunk.txt [step_cap]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <dlfcn.h>

/* ---- Minimal inline OpenCL type definitions ---- */
typedef signed int     cl_int;
typedef unsigned int   cl_uint;
typedef signed long    cl_long;
typedef unsigned long  cl_ulong;
typedef cl_uint        cl_bool;
typedef cl_ulong       cl_bitfield;
typedef cl_bitfield    cl_device_type;
typedef cl_bitfield    cl_command_queue_properties;
typedef cl_uint        cl_device_info;
typedef cl_uint        cl_program_build_info;
typedef cl_bitfield    cl_mem_flags;
typedef void *         cl_platform_id;
typedef void *         cl_device_id;
typedef void *         cl_context;
typedef void *         cl_command_queue;
typedef void *         cl_mem;
typedef void *         cl_program;
typedef void *         cl_kernel;
typedef void *         cl_event;

#define CL_SUCCESS                      0
#define CL_DEVICE_TYPE_GPU              (1 << 2)
#define CL_DEVICE_TYPE_ALL              0xFFFFFFFF
#define CL_DEVICE_NAME                  0x102B
#define CL_MEM_READ_ONLY               (1 << 2)
#define CL_MEM_WRITE_ONLY              (1 << 1)
#define CL_MEM_COPY_HOST_PTR           (1 << 5)
#define CL_TRUE                         1
#define CL_PROGRAM_BUILD_LOG            0x1183

/* ---- Function pointer typedefs ---- */
typedef cl_int (*fn_clGetPlatformIDs)(cl_uint, cl_platform_id*, cl_uint*);
typedef cl_int (*fn_clGetDeviceIDs)(cl_platform_id, cl_device_type, cl_uint, cl_device_id*, cl_uint*);
typedef cl_int (*fn_clGetDeviceInfo)(cl_device_id, cl_device_info, size_t, void*, size_t*);
typedef cl_context (*fn_clCreateContext)(void*, cl_uint, const cl_device_id*, void*, void*, cl_int*);
typedef cl_command_queue (*fn_clCreateCommandQueue)(cl_context, cl_device_id, cl_command_queue_properties, cl_int*);
typedef cl_program (*fn_clCreateProgramWithSource)(cl_context, cl_uint, const char**, const size_t*, cl_int*);
typedef cl_int (*fn_clBuildProgram)(cl_program, cl_uint, const cl_device_id*, const char*, void*, void*);
typedef cl_int (*fn_clGetProgramBuildInfo)(cl_program, cl_device_id, cl_program_build_info, size_t, void*, size_t*);
typedef cl_kernel (*fn_clCreateKernel)(cl_program, const char*, cl_int*);
typedef cl_int (*fn_clSetKernelArg)(cl_kernel, cl_uint, size_t, const void*);
typedef cl_mem (*fn_clCreateBuffer)(cl_context, cl_mem_flags, size_t, void*, cl_int*);
typedef cl_int (*fn_clEnqueueNDRangeKernel)(cl_command_queue, cl_kernel, cl_uint, const size_t*, const size_t*, const size_t*, cl_uint, const cl_event*, cl_event*);
typedef cl_int (*fn_clFinish)(cl_command_queue);
typedef cl_int (*fn_clEnqueueReadBuffer)(cl_command_queue, cl_mem, cl_bool, size_t, size_t, void*, cl_uint, const cl_event*, cl_event*);
typedef cl_int (*fn_clReleaseMemObject)(cl_mem);
typedef cl_int (*fn_clReleaseKernel)(cl_kernel);
typedef cl_int (*fn_clReleaseProgram)(cl_program);
typedef cl_int (*fn_clReleaseCommandQueue)(cl_command_queue);
typedef cl_int (*fn_clReleaseContext)(cl_context);

/* Global function pointers */
fn_clGetPlatformIDs p_clGetPlatformIDs;
fn_clGetDeviceIDs p_clGetDeviceIDs;
fn_clGetDeviceInfo p_clGetDeviceInfo;
fn_clCreateContext p_clCreateContext;
fn_clCreateCommandQueue p_clCreateCommandQueue;
fn_clCreateProgramWithSource p_clCreateProgramWithSource;
fn_clBuildProgram p_clBuildProgram;
fn_clGetProgramBuildInfo p_clGetProgramBuildInfo;
fn_clCreateKernel p_clCreateKernel;
fn_clSetKernelArg p_clSetKernelArg;
fn_clCreateBuffer p_clCreateBuffer;
fn_clEnqueueNDRangeKernel p_clEnqueueNDRangeKernel;
fn_clFinish p_clFinish;
fn_clEnqueueReadBuffer p_clEnqueueReadBuffer;
fn_clReleaseMemObject p_clReleaseMemObject;
fn_clReleaseKernel p_clReleaseKernel;
fn_clReleaseProgram p_clReleaseProgram;
fn_clReleaseCommandQueue p_clReleaseCommandQueue;
fn_clReleaseContext p_clReleaseContext;

int load_opencl(void) {
    void *lib = dlopen("/vendor/lib64/libOpenCL.so", RTLD_NOW);
    if (!lib) lib = dlopen("/system/vendor/lib64/libOpenCL.so", RTLD_NOW);
    if (!lib) lib = dlopen("libOpenCL.so", RTLD_NOW);
    if (!lib) { printf("Cannot load libOpenCL.so: %s\n", dlerror()); return 0; }

    p_clGetPlatformIDs = (fn_clGetPlatformIDs)dlsym(lib, "clGetPlatformIDs");
    p_clGetDeviceIDs = (fn_clGetDeviceIDs)dlsym(lib, "clGetDeviceIDs");
    p_clGetDeviceInfo = (fn_clGetDeviceInfo)dlsym(lib, "clGetDeviceInfo");
    p_clCreateContext = (fn_clCreateContext)dlsym(lib, "clCreateContext");
    p_clCreateCommandQueue = (fn_clCreateCommandQueue)dlsym(lib, "clCreateCommandQueue");
    p_clCreateProgramWithSource = (fn_clCreateProgramWithSource)dlsym(lib, "clCreateProgramWithSource");
    p_clBuildProgram = (fn_clBuildProgram)dlsym(lib, "clBuildProgram");
    p_clGetProgramBuildInfo = (fn_clGetProgramBuildInfo)dlsym(lib, "clGetProgramBuildInfo");
    p_clCreateKernel = (fn_clCreateKernel)dlsym(lib, "clCreateKernel");
    p_clSetKernelArg = (fn_clSetKernelArg)dlsym(lib, "clSetKernelArg");
    p_clCreateBuffer = (fn_clCreateBuffer)dlsym(lib, "clCreateBuffer");
    p_clEnqueueNDRangeKernel = (fn_clEnqueueNDRangeKernel)dlsym(lib, "clEnqueueNDRangeKernel");
    p_clFinish = (fn_clFinish)dlsym(lib, "clFinish");
    p_clEnqueueReadBuffer = (fn_clEnqueueReadBuffer)dlsym(lib, "clEnqueueReadBuffer");
    p_clReleaseMemObject = (fn_clReleaseMemObject)dlsym(lib, "clReleaseMemObject");
    p_clReleaseKernel = (fn_clReleaseKernel)dlsym(lib, "clReleaseKernel");
    p_clReleaseProgram = (fn_clReleaseProgram)dlsym(lib, "clReleaseProgram");
    p_clReleaseCommandQueue = (fn_clReleaseCommandQueue)dlsym(lib, "clReleaseCommandQueue");
    p_clReleaseContext = (fn_clReleaseContext)dlsym(lib, "clReleaseContext");

    if (!p_clGetPlatformIDs || !p_clCreateContext || !p_clCreateKernel) {
        printf("Missing OpenCL symbols\n");
        return 0;
    }
    return 1;
}

const char *kernel_src =
"__kernel void erdos_straus(\n"
"    __global const long *ns,\n"
"    __global long *results,\n"
"    const int step_cap,\n"
"    const int count)\n"
"{\n"
"    int gid = get_global_id(0);\n"
"    if (gid >= count) return;\n"
"\n"
"    long n = ns[gid];\n"
"    int base = gid * 5;\n"
"    results[base+0] = n;\n"
"    results[base+1] = 0;\n"
"    results[base+2] = 0;\n"
"    results[base+3] = 0;\n"
"    results[base+4] = 0;\n"
"\n"
"    if (n <= 1) return;\n"
"\n"
"    int steps = 0;\n"
"    long x_min = (n + 3) / 4;\n"
"    long x_max = n;\n"
"\n"
"    for (long x = x_min; x <= x_max; x++) {\n"
"        long num_r = 4 * x - n;\n"
"        if (num_r <= 0) {\n"
"            steps++;\n"
"            if (steps >= step_cap) return;\n"
"            continue;\n"
"        }\n"
"        long den_r = n * x;\n"
"        long y_min = (den_r + num_r - 1) / num_r;\n"
"        long y_max = 2 * den_r / num_r;\n"
"        if (x > y_min) y_min = x;\n"
"\n"
"        int y_steps = 0;\n"
"        for (long y = y_min; y <= y_max; y++) {\n"
"            steps++;\n"
"            y_steps++;\n"
"            if (steps >= step_cap) return;\n"
"            if (y_steps >= 1000000) break;\n"
"\n"
"            long denom_z = num_r * y - den_r;\n"
"            if (denom_z <= 0) continue;\n"
"            long num_z = den_r * y;\n"
"            if (num_z % denom_z == 0) {\n"
"                long z = num_z / denom_z;\n"
"                if (z >= y) {\n"
"                    results[base+1] = x;\n"
"                    results[base+2] = y;\n"
"                    results[base+3] = z;\n"
"                    results[base+4] = 1;\n"
"                    return;\n"
"                }\n"
"            }\n"
"        }\n"
"    }\n"
"}\n";

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("Usage: %s <chunk_file> [step_cap]\n", argv[0]);
        return 1;
    }

    const char *chunk_file = argv[1];
    int step_cap = argc >= 3 ? atoi(argv[2]) : 10000000;

    if (!load_opencl()) return 1;
    printf("[phone-gpu] OpenCL loaded\n");

    /* Read n values */
    FILE *fp = fopen(chunk_file, "r");
    if (!fp) { printf("Cannot open %s\n", chunk_file); return 1; }

    int capacity = 300000;
    long *all_ns = (long *)malloc(capacity * sizeof(long));
    int total = 0;
    char line[64];
    while (fgets(line, sizeof(line), fp)) {
        if (line[0] == '\n' || line[0] == '\0') continue;
        if (total >= capacity) {
            capacity *= 2;
            all_ns = (long *)realloc(all_ns, capacity * sizeof(long));
        }
        all_ns[total++] = atol(line);
    }
    fclose(fp);
    printf("[phone-gpu] %d values, step_cap=%d\n", total, step_cap);

    /* OpenCL setup */
    cl_platform_id platform;
    cl_device_id device;
    cl_int err;

    err = p_clGetPlatformIDs(1, &platform, NULL);
    if (err != CL_SUCCESS) { printf("No platform: %d\n", err); return 1; }

    err = p_clGetDeviceIDs(platform, CL_DEVICE_TYPE_GPU, 1, &device, NULL);
    if (err != CL_SUCCESS) {
        printf("No GPU, trying ALL...\n");
        err = p_clGetDeviceIDs(platform, CL_DEVICE_TYPE_ALL, 1, &device, NULL);
        if (err != CL_SUCCESS) { printf("No device: %d\n", err); return 1; }
    }

    char dev_name[256];
    p_clGetDeviceInfo(device, CL_DEVICE_NAME, sizeof(dev_name), dev_name, NULL);
    printf("[phone-gpu] Device: %s\n", dev_name);

    cl_context ctx = p_clCreateContext(NULL, 1, &device, NULL, NULL, &err);
    cl_command_queue queue = p_clCreateCommandQueue(ctx, device, 0, &err);

    cl_program program = p_clCreateProgramWithSource(ctx, 1, &kernel_src, NULL, &err);
    err = p_clBuildProgram(program, 1, &device, NULL, NULL, NULL);
    if (err != CL_SUCCESS) {
        char log[4096];
        p_clGetProgramBuildInfo(program, device, CL_PROGRAM_BUILD_LOG, sizeof(log), log, NULL);
        printf("Build error:\n%s\n", log);
        return 1;
    }
    cl_kernel kernel = p_clCreateKernel(program, "erdos_straus", &err);
    printf("[phone-gpu] Kernel ready\n");

    /* Process in batches */
    int batch_size = 64;
    int solved_total = 0;
    time_t t0 = time(NULL);

    FILE *out = fopen("phone_gpu_results.csv", "w");
    fprintf(out, "n,x,y,z,solved\n");

    for (int offset = 0; offset < total; offset += batch_size) {
        int count = batch_size;
        if (offset + count > total) count = total - offset;

        cl_mem buf_ns = p_clCreateBuffer(ctx, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
                                         count * sizeof(long), &all_ns[offset], &err);
        long *results = (long *)calloc(count * 5, sizeof(long));
        cl_mem buf_res = p_clCreateBuffer(ctx, CL_MEM_WRITE_ONLY,
                                          count * 5 * sizeof(long), NULL, &err);

        p_clSetKernelArg(kernel, 0, sizeof(cl_mem), &buf_ns);
        p_clSetKernelArg(kernel, 1, sizeof(cl_mem), &buf_res);
        p_clSetKernelArg(kernel, 2, sizeof(int), &step_cap);
        p_clSetKernelArg(kernel, 3, sizeof(int), &count);

        size_t global = count;
        p_clEnqueueNDRangeKernel(queue, kernel, 1, NULL, &global, NULL, 0, NULL, NULL);
        p_clFinish(queue);

        p_clEnqueueReadBuffer(queue, buf_res, CL_TRUE, 0,
                             count * 5 * sizeof(long), results, 0, NULL, NULL);

        int batch_solved = 0;
        for (int i = 0; i < count; i++) {
            int b = i * 5;
            if (results[b+4]) {
                batch_solved++;
                solved_total++;
            }
            fprintf(out, "%ld,%ld,%ld,%ld,%d\n",
                    results[b], results[b+1], results[b+2], results[b+3],
                    (int)results[b+4]);
        }

        int batch_num = offset / batch_size + 1;
        int total_batches = (total + batch_size - 1) / batch_size;
        if (batch_num % 50 == 0 || batch_num == total_batches) {
            printf("  [%d/%d] %d/%d (total: %d)\n",
                   batch_num, total_batches, batch_solved, count, solved_total);
            fflush(out);
        }

        p_clReleaseMemObject(buf_ns);
        p_clReleaseMemObject(buf_res);
        free(results);
    }

    fclose(out);
    time_t elapsed = time(NULL) - t0;
    printf("\n[phone-gpu] Done in %lds\n", elapsed);
    printf("[phone-gpu] Solved: %d / %d\n", solved_total, total);

    p_clReleaseKernel(kernel);
    p_clReleaseProgram(program);
    p_clReleaseCommandQueue(queue);
    p_clReleaseContext(ctx);
    free(all_ns);
    return 0;
}
