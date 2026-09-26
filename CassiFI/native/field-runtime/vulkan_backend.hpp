#pragma once

#include "compare_set_shader.hpp"
#include "field_image.hpp"
#include "add_constant_shader.hpp"
#include "reduce_shader.hpp"

#include <atomic>
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <memory>
#include <span>
#include <string>
#include <vector>
#include <array>
#include <limits>
#include <string_view>
#include <unordered_map>

#ifdef CASSIFI_HAVE_VULKAN
#include <vulkan/vulkan.h>
#endif

namespace cassifi::field_runtime {

namespace {

constexpr char kHexDigits[]="0123456789abcdef";

std::string hex_number(std::uint32_t value) {
    std::string text="0x";
    for(int shift=28;shift>=0;shift-=4){
        const unsigned nibble=(value>>shift)&0xFU;
        if(text.size()>2||nibble!=0) text.push_back(kHexDigits[nibble]);
    }
    if(text.size()==2) text.push_back('0');
    return text;
}

} // namespace

struct DeviceMemoryReport {
    bool heaps_available{};      // selected heap identity/size can be determined
    bool budget_available{};     // measured budget/usage from VK_EXT_memory_budget
    bool gpu_field_words_available{};
    bool gpu_field_memory_type_available{};
    bool gpu_field_device_local{};
    std::uint32_t gpu_field_memory_type_index{UINT32_MAX};
    std::uint32_t gpu_field_heap_index{UINT32_MAX};
    std::uint32_t gpu_field_memory_property_flags{};
    std::uint32_t gpu_field_memory_heap_flags{};
    std::uint64_t heap_total_bytes{};
    std::uint64_t heap_budget_bytes{};
    std::uint64_t heap_usage_bytes{};
    std::uint64_t gpu_field_batches{};
    std::uint64_t gpu_field_host_upload_bytes{};
    std::uint64_t gpu_field_changed_page_export_bytes{};
    std::uint64_t gpu_field_retained_bytes{};
    std::string note{};          // explicit measured/unavailable marker; never guessed free VRAM
};

struct ReduceResult {
    std::uint64_t sum{};
    std::uint64_t count{};
    std::string placement{};
};

class VulkanBackend {
public:
    explicit VulkanBackend(std::uint32_t device_index = 0, bool enabled = true) : device_index_(device_index) {
        if (!enabled) { reason_="disabled by --cpu-only"; return; }
#ifdef CASSIFI_HAVE_VULKAN
        VkApplicationInfo application{VK_STRUCTURE_TYPE_APPLICATION_INFO};
        application.pApplicationName = "CassiFI field-runtime";
        application.applicationVersion = VK_MAKE_VERSION(1,0,0);
        application.pEngineName = "CassiFI";
        application.engineVersion = VK_MAKE_VERSION(1,0,0);
        application.apiVersion = VK_API_VERSION_1_2;
        std::vector<const char*> instance_extensions;
        std::uint32_t instance_extension_count=0;
        if(vkEnumerateInstanceExtensionProperties(nullptr,&instance_extension_count,nullptr)==VK_SUCCESS&&instance_extension_count){
            std::vector<VkExtensionProperties> extensions(instance_extension_count);
            if(vkEnumerateInstanceExtensionProperties(nullptr,&instance_extension_count,extensions.data())==VK_SUCCESS){
                for(const auto& extension:extensions) if(std::strcmp(extension.extensionName,VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_EXTENSION_NAME)==0){instance_extensions.push_back(VK_KHR_GET_PHYSICAL_DEVICE_PROPERTIES_2_EXTENSION_NAME);break;}
            }
        }
        VkInstanceCreateInfo instance_info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
        instance_info.pApplicationInfo = &application;
        instance_info.enabledExtensionCount=static_cast<std::uint32_t>(instance_extensions.size());
        instance_info.ppEnabledExtensionNames=instance_extensions.data();
        if (vkCreateInstance(&instance_info, nullptr, &instance_) != VK_SUCCESS) { reason_="vkCreateInstance failed"; return; }
        // Core 1.1+ entry points are not exported by vulkan-1.dll; resolve the KHR alias through the loader.
        properties2_=reinterpret_cast<PFN_vkGetPhysicalDeviceProperties2KHR>(vkGetInstanceProcAddr(instance_,"vkGetPhysicalDeviceProperties2KHR"));
        memory_properties2_=reinterpret_cast<PFN_vkGetPhysicalDeviceMemoryProperties2KHR>(vkGetInstanceProcAddr(instance_,"vkGetPhysicalDeviceMemoryProperties2KHR"));
        if(!memory_properties2_) memory_properties2_=reinterpret_cast<PFN_vkGetPhysicalDeviceMemoryProperties2KHR>(vkGetInstanceProcAddr(instance_,"vkGetPhysicalDeviceMemoryProperties2"));
        std::uint32_t count=0;
        if(vkEnumeratePhysicalDevices(instance_,&count,nullptr)!=VK_SUCCESS||!count){reason_="no Vulkan physical device";return;}
        std::vector<VkPhysicalDevice> devices(count);
        if(vkEnumeratePhysicalDevices(instance_,&count,devices.data())!=VK_SUCCESS||device_index>=count){reason_="Vulkan device index is unavailable";return;}
        physical_=devices[device_index];
        VkPhysicalDeviceProperties properties{}; vkGetPhysicalDeviceProperties(physical_,&properties); device_name_=properties.deviceName;
        vendor_id_=properties.vendorID; device_id_=properties.deviceID; driver_version_=properties.driverVersion;
        if(properties2_){
            VkPhysicalDeviceIDProperties id_properties{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ID_PROPERTIES};
            VkPhysicalDeviceProperties2 properties2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};
            properties2.pNext=&id_properties;
            properties2_(physical_,&properties2);
            bool present=false; for(const auto byte:id_properties.deviceUUID) present=present||byte!=0;
            if(present){ device_identity_.reserve(VK_UUID_SIZE*2U); for(const auto byte:id_properties.deviceUUID){device_identity_.push_back(kHexDigits[byte>>4U]);device_identity_.push_back(kHexDigits[byte&0xFU]);} identity_kind_="device-uuid-stable"; }
        }
        if(device_identity_.empty()){
            // No UUID: fall back to vendor/device ids plus the launch-time index; explicitly NOT stable across sessions.
            device_identity_="vendor:"+hex_number(vendor_id_)+":device:"+hex_number(device_id_)+":driver:"+hex_number(driver_version_)+":index:"+std::to_string(device_index_);
            identity_kind_="vendor-device-index-session";
        }
#ifdef VK_EXT_MEMORY_BUDGET_EXTENSION_NAME
        std::uint32_t device_extension_count=0;
        if(vkEnumerateDeviceExtensionProperties(physical_,nullptr,&device_extension_count,nullptr)==VK_SUCCESS&&device_extension_count){
            std::vector<VkExtensionProperties> extensions(device_extension_count);
            if(vkEnumerateDeviceExtensionProperties(physical_,nullptr,&device_extension_count,extensions.data())==VK_SUCCESS){
                for(const auto& extension:extensions) if(std::strcmp(extension.extensionName,VK_EXT_MEMORY_BUDGET_EXTENSION_NAME)==0){budget_extension_=true;break;}
            }
        }
#endif
        VkPhysicalDeviceMemoryProperties memory_properties{}; vkGetPhysicalDeviceMemoryProperties(physical_,&memory_properties);
        std::uint32_t default_type=UINT32_MAX;bool default_device_local=false;
        for(std::uint32_t i=0;i<memory_properties.memoryTypeCount;++i){
            const auto flags=memory_properties.memoryTypes[i].propertyFlags;
            if((flags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))!=
                    (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) continue;
            const bool device_local=(flags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)!=0;
            if(default_type==UINT32_MAX||(device_local&&!default_device_local)){
                default_type=i;default_device_local=device_local;
            }
        }
        if(default_type!=UINT32_MAX) heaps_available_=true;
        std::uint32_t queue_count=0; vkGetPhysicalDeviceQueueFamilyProperties(physical_,&queue_count,nullptr);
        std::vector<VkQueueFamilyProperties> queues(queue_count); vkGetPhysicalDeviceQueueFamilyProperties(physical_,&queue_count,queues.data());
        bool found=false; for(std::uint32_t i=0;i<queue_count;++i) if(queues[i].queueFlags&VK_QUEUE_COMPUTE_BIT){queue_family_=i;found=true;break;}
        if(!found){reason_="selected Vulkan device has no compute queue";return;}
        const float priority=1.0F; VkDeviceQueueCreateInfo queue_info{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO}; queue_info.queueFamilyIndex=queue_family_;queue_info.queueCount=1;queue_info.pQueuePriorities=&priority;
        VkDeviceCreateInfo device_info{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};device_info.queueCreateInfoCount=1;device_info.pQueueCreateInfos=&queue_info;device_info.pEnabledFeatures=nullptr;
#ifdef VK_EXT_MEMORY_BUDGET_EXTENSION_NAME
        const char* device_extensions[]={VK_EXT_MEMORY_BUDGET_EXTENSION_NAME};
        if(budget_extension_){device_info.enabledExtensionCount=1;device_info.ppEnabledExtensionNames=device_extensions;}
#endif
        if(vkCreateDevice(physical_,&device_info,nullptr,&device_)!=VK_SUCCESS){reason_="vkCreateDevice failed";return;}
        vkGetDeviceQueue(device_,queue_family_,0,&queue_);
        VkCommandPoolCreateInfo pool_info{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};pool_info.flags=VK_COMMAND_POOL_CREATE_TRANSIENT_BIT|VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;pool_info.queueFamilyIndex=queue_family_;
        if(vkCreateCommandPool(device_,&pool_info,nullptr,&command_pool_)!=VK_SUCCESS){reason_="vkCreateCommandPool failed";return;}
        available_=true;reason_="ready";
#else
        (void)device_index;
        reason_="built without Vulkan SDK";
#endif
    }
    VulkanBackend(const VulkanBackend&)=delete;
    VulkanBackend& operator=(const VulkanBackend&)=delete;
    ~VulkanBackend(){
#ifdef CASSIFI_HAVE_VULKAN
        if(device_!=VK_NULL_HANDLE) vkDeviceWaitIdle(device_);
        release_resident();
        release_all_owner_images();
        if(command_pool_!=VK_NULL_HANDLE) vkDestroyCommandPool(device_,command_pool_,nullptr);
        if(device_!=VK_NULL_HANDLE) vkDestroyDevice(device_,nullptr);
        if(instance_!=VK_NULL_HANDLE) vkDestroyInstance(instance_,nullptr);
#endif
    }
    [[nodiscard]] bool available() const noexcept{return available_;}
    [[nodiscard]] const std::string& reason() const noexcept{return reason_;}
    [[nodiscard]] const std::string& device_name() const noexcept{return device_name_;}
    // Selected Vulkan physical device index (the launch --device value when enumeration succeeded).
    [[nodiscard]] std::uint32_t device_index() const noexcept{return device_index_;}
    // deviceUUID hex when the driver provides one, else vendor/device/driver ids plus the launch index.
    [[nodiscard]] const std::string& device_identity() const noexcept{return device_identity_;}
    // "device-uuid-stable" (persistent physical device identity) or "vendor-device-index-session" (not stable across sessions).
    [[nodiscard]] const std::string& device_identity_kind() const noexcept{return identity_kind_;}

    // Physical-device queries only: reads no Vulkan object owned by apply()/reduce(), so it is safe to call
    // concurrently with candidate work and is invoked solely from status/probe handlers, never per token.
    // heap budget/usage is per physical device and per heap for THIS runtime instance; it is not global GPU
    // accounting across other engines on the same adapter.
    [[nodiscard]] DeviceMemoryReport memory_report() const {
        DeviceMemoryReport report;
        report.gpu_field_words_available=available_.load(std::memory_order_relaxed);
        report.gpu_field_batches=gpu_field_batches_.load(std::memory_order_relaxed);
        report.gpu_field_host_upload_bytes=gpu_field_host_upload_bytes_.load(std::memory_order_relaxed);
        report.gpu_field_changed_page_export_bytes=gpu_field_changed_page_export_bytes_.load(std::memory_order_relaxed);
        report.gpu_field_retained_bytes=field_resident_bytes();
#ifdef CASSIFI_HAVE_VULKAN
        if(!available_.load(std::memory_order_relaxed)){report.note="unavailable";return report;}
        if(!heaps_available_){report.note="unavailable: no coherent host-visible candidate memory heap";return report;}
        VkPhysicalDeviceMemoryProperties memory_properties{};vkGetPhysicalDeviceMemoryProperties(physical_,&memory_properties);
        const auto memory_selection=selected_memory_metadata_.load(std::memory_order_acquire);
        if(memory_selection==UINT64_MAX){report.note="no field buffer memory type has been selected";return report;}
        report.heaps_available=true;
        const auto heap_index=static_cast<std::uint32_t>((memory_selection>>8U)&0xffU);
        const auto memory_flags=static_cast<std::uint32_t>(memory_selection>>16U);
        report.gpu_field_memory_type_available=true;
        report.gpu_field_memory_type_index=static_cast<std::uint32_t>(memory_selection&0xffU);
        report.gpu_field_heap_index=heap_index;
        report.gpu_field_memory_property_flags=memory_flags;
        report.gpu_field_memory_heap_flags=memory_properties.memoryHeaps[heap_index].flags;
        report.gpu_field_device_local=(memory_flags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)!=0&&
            (report.gpu_field_memory_heap_flags&VK_MEMORY_HEAP_DEVICE_LOCAL_BIT)!=0;
        report.heap_total_bytes=memory_properties.memoryHeaps[heap_index].size;
#ifdef VK_EXT_MEMORY_BUDGET_EXTENSION_NAME
        if(budget_extension_&&memory_properties2_){
            VkPhysicalDeviceMemoryBudgetPropertiesEXT budget{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_BUDGET_PROPERTIES_EXT};
            VkPhysicalDeviceMemoryProperties2 memory_properties2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_PROPERTIES_2};
            memory_properties2.pNext=&budget;memory_properties2_(physical_,&memory_properties2);
            report.budget_available=true;
            report.heap_budget_bytes=budget.heapBudget[heap_index];
            report.heap_usage_bytes=budget.heapUsage[heap_index];
            if(report.heap_budget_bytes==0&&report.heap_usage_bytes==0){
                // Some drivers advertise VK_EXT_memory_budget but return no data; report unavailable, not zeros.
                report.budget_available=false;
                report.note="VK_EXT_memory_budget present but driver reported no budget data";
                return report;
            }
            report.note="measured";
            return report;
        }
#endif
        report.note="VK_EXT_memory_budget unavailable; budget and usage not reported";
#else
        report.note="unavailable: "+reason_;
#endif
        return report;
    }

    bool apply(PackedImage& image,std::span<const WordOperation> operations){
        if(operations.empty()) return false;
#ifndef CASSIFI_HAVE_VULKAN
        apply_word_operations(image,operations);
        return false;
#else
        if(!available_||image.canonical_bytes()>kMaxFieldBytes||image.packed_bytes()>kMaxFieldBytes){
            discard_candidate(image.owner_id);
            apply_word_operations(image,operations);
            return false;
        }
        try {
            return apply_gpu_candidate(image,operations);
        } catch(const DeviceLost&) {
            recover_after_device_loss();
            if(available_){
                try {
                    return apply_gpu_candidate(image,operations);
                } catch(const DeviceLost&) {
                    recover_after_device_loss();
                } catch(const GpuExecutionError&) {
                }
            }
            discard_candidate(image.owner_id);
            apply_word_operations(image,operations);
            return false;
        } catch(const GpuExecutionError&) {
            discard_candidate(image.owner_id);
            apply_word_operations(image,operations);
            return false;
        }
#endif
    }

    void discard_candidate(const std::string& owner_id) noexcept {
#ifdef CASSIFI_HAVE_VULKAN
        const auto found=owner_images_.find(owner_id);
        if(found!=owner_images_.end()){
            if(found->second.pending.buffer!=VK_NULL_HANDLE) gpu_field_retained_bytes_.fetch_sub(found->second.pending.allocation_bytes,std::memory_order_relaxed);
            release_image(found->second.pending);
            found->second.pending={};found->second.pending_valid=false;
            if(found->second.committed.buffer==VK_NULL_HANDLE) owner_images_.erase(found);
        }
#else
        (void)owner_id;
#endif
    }

    // This is called only after the owner has durably acknowledged publication.
    // It performs no Vulkan work or allocation; false means the exact successor
    // is not currently cached and the next GPU use will rebuild it from host bytes.
    bool commit_candidate(const PackedImage& predecessor,const PackedImage& accepted) noexcept {
#ifdef CASSIFI_HAVE_VULKAN
        try {
            if(!valid_successor(predecessor,accepted)){
                discard_candidate(predecessor.owner_id);
                return false;
            }
            const auto found=owner_images_.find(predecessor.owner_id);
            if(found==owner_images_.end()) return false;
            auto& entry=found->second;
            const auto predecessor_version=version_for(predecessor);
            const auto accepted_version=version_for(accepted);
            if(entry.pending.buffer!=VK_NULL_HANDLE){
                const bool pending_matches=entry.pending_valid&&
                    same_version(entry.pending_base,predecessor_version)&&
                    same_content(entry.pending.version,accepted_version);
                if(!pending_matches){
                    gpu_field_retained_bytes_.fetch_sub(entry.pending.allocation_bytes,std::memory_order_relaxed);
                    release_image(entry.pending);entry.pending_valid=false;entry.pending_base={};
                    if(entry.committed.buffer==VK_NULL_HANDLE) owner_images_.erase(found);
                    return false;
                }
                if(entry.committed.buffer!=VK_NULL_HANDLE) gpu_field_retained_bytes_.fetch_sub(entry.committed.allocation_bytes,std::memory_order_relaxed);
                release_image(entry.committed);
                entry.committed=std::move(entry.pending);
                entry.committed.version=accepted_version;entry.committed.version_valid=true;
                entry.pending={};entry.pending_valid=false;
                return true;
            }
            if(entry.committed.buffer==VK_NULL_HANDLE||
                    !same_version(entry.committed.version,predecessor_version)||
                    !same_content(entry.committed.version,accepted_version)) return false;
            entry.committed.version=accepted_version;
            return true;
        } catch(...) {
            discard_candidate(predecessor.owner_id);
            return false;
        }
#else
        (void)predecessor;(void)accepted;return false;
#endif
    }
    // The first reduction uploads an immutable, versioned candidate image.
    // Later reductions reuse its device buffer and read back only exact u64 partials.
    // A different source, page map, or fence replaces the resident copy; the
    // canonical host candidate remains unchanged.
    ReduceResult reduce(const PackedImage& image, std::uint64_t first_word, std::uint64_t count) {
#ifndef CASSIFI_HAVE_VULKAN
        return {sum_words(image.words, first_word, count), count, "native-cpu"};
#else
        if (!available_ || count == 0 || first_word > image.words.size() || count > image.words.size() - static_cast<std::size_t>(first_word)) return {sum_words(image.words, first_word, count), count, "native-cpu"};
        if (image.packed_bytes() > kMaxFieldBytes || image.words.size() > kMaxFieldBytes / sizeof(std::uint32_t)) return {sum_words(image.words, first_word, count), count, "native-cpu"};
        const VkDeviceSize bytes = VkDeviceSize(image.packed_bytes());
        const auto version=version_for(image);
        VkBuffer field_buffer=exact_owner_buffer(image,version);
        if(field_buffer==VK_NULL_HANDLE){
            try {
                ensure_resident(image,version,bytes);
            } catch(const DeviceLost&) {
                recover_after_device_loss();
                return {sum_words(image.words,first_word,count),count,"native-cpu"};
            }
            field_buffer=resident_.buffer;
        }
        VkPhysicalDeviceProperties properties{};vkGetPhysicalDeviceProperties(physical_, &properties);
        const auto max_groups = std::uint32_t(std::min<std::uint64_t>(properties.limits.maxComputeWorkGroupCount[0], 65535U));
        auto groups = std::uint32_t((count + 255U) / 256U);
        if (groups > max_groups) groups = max_groups;
        VkBuffer partials = VK_NULL_HANDLE;VkDeviceMemory partials_memory = VK_NULL_HANDLE;
        VkShaderModule shader = VK_NULL_HANDLE;VkDescriptorSetLayout descriptor_layout = VK_NULL_HANDLE;VkPipelineLayout pipeline_layout = VK_NULL_HANDLE;VkPipeline pipeline = VK_NULL_HANDLE;VkDescriptorPool descriptor_pool = VK_NULL_HANDLE;
        VkDescriptorSet descriptor_set = VK_NULL_HANDLE;VkCommandBuffer command = VK_NULL_HANDLE;VkFence fence = VK_NULL_HANDLE;
        const VkDeviceSize partial_bytes = VkDeviceSize(groups) * 2U * sizeof(std::uint32_t);
        auto cleanup = [&]() noexcept {if (fence)vkDestroyFence(device_, fence, nullptr);if (command)vkFreeCommandBuffers(device_, command_pool_, 1, &command);if (descriptor_pool)vkDestroyDescriptorPool(device_, descriptor_pool, nullptr);if (pipeline)vkDestroyPipeline(device_, pipeline, nullptr);if (pipeline_layout)vkDestroyPipelineLayout(device_, pipeline_layout, nullptr);if (descriptor_layout)vkDestroyDescriptorSetLayout(device_, descriptor_layout, nullptr);if (shader)vkDestroyShaderModule(device_, shader, nullptr);if (partials)vkDestroyBuffer(device_, partials, nullptr);if (partials_memory)vkFreeMemory(device_, partials_memory, nullptr);};
        try {
            VkBufferCreateInfo partial_info{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};partial_info.size = partial_bytes;partial_info.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;partial_info.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
            check_vk(vkCreateBuffer(device_,&partial_info,nullptr,&partials),"Vulkan reduction partial buffer allocation failed");
            VkMemoryRequirements partial_requirements{};vkGetBufferMemoryRequirements(device_, partials, &partial_requirements);
            VkPhysicalDeviceMemoryProperties memory_properties{};vkGetPhysicalDeviceMemoryProperties(physical_, &memory_properties);
            std::uint32_t memory_type = UINT32_MAX;
            for (std::uint32_t i = 0; i < memory_properties.memoryTypeCount; ++i) if ((partial_requirements.memoryTypeBits & (1U << i)) && (memory_properties.memoryTypes[i].propertyFlags & (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) == (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) { memory_type = i; break; }
            if (memory_type == UINT32_MAX) throw ProtocolError("Vulkan device has no coherent host-visible reduction memory");
            VkMemoryAllocateInfo partial_allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};partial_allocation.allocationSize = partial_requirements.size;partial_allocation.memoryTypeIndex = memory_type;
            check_vk(vkAllocateMemory(device_,&partial_allocation,nullptr,&partials_memory),"Vulkan reduction partial memory allocation failed");check_vk(vkBindBufferMemory(device_,partials,partials_memory,0),"Vulkan reduction partial memory binding failed");
            VkShaderModuleCreateInfo shader_info{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};shader_info.codeSize = kReduceShader.size() * sizeof(std::uint32_t);shader_info.pCode = kReduceShader.data();
            check_vk(vkCreateShaderModule(device_,&shader_info,nullptr,&shader),"Vulkan reduction shader creation failed");
            std::array<VkDescriptorSetLayoutBinding, 2> bindings{};
            bindings[0].binding = 0;bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;bindings[0].descriptorCount = 1;bindings[0].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
            bindings[1].binding = 1;bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;bindings[1].descriptorCount = 1;bindings[1].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
            VkDescriptorSetLayoutCreateInfo descriptor_info{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};descriptor_info.bindingCount = 2;descriptor_info.pBindings = bindings.data();
            check_vk(vkCreateDescriptorSetLayout(device_,&descriptor_info,nullptr,&descriptor_layout),"Vulkan reduction descriptor layout creation failed");
            VkPushConstantRange push{};push.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;push.offset = 0;push.size = 2U * sizeof(std::uint32_t);
            VkPipelineLayoutCreateInfo layout_info{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};layout_info.setLayoutCount = 1;layout_info.pSetLayouts = &descriptor_layout;layout_info.pushConstantRangeCount = 1;layout_info.pPushConstantRanges = &push;
            check_vk(vkCreatePipelineLayout(device_,&layout_info,nullptr,&pipeline_layout),"Vulkan reduction pipeline layout creation failed");
            VkPipelineShaderStageCreateInfo stage{VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;stage.module = shader;stage.pName = "main";
            VkComputePipelineCreateInfo pipeline_info{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};pipeline_info.stage = stage;pipeline_info.layout = pipeline_layout;
            check_vk(vkCreateComputePipelines(device_,VK_NULL_HANDLE,1,&pipeline_info,nullptr,&pipeline),"Vulkan reduction compute pipeline creation failed");
            VkDescriptorPoolSize pool_sizes[]{{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1}, {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1}};
            VkDescriptorPoolCreateInfo pool_info{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};pool_info.maxSets = 1;pool_info.poolSizeCount = 2;pool_info.pPoolSizes = pool_sizes;
            check_vk(vkCreateDescriptorPool(device_,&pool_info,nullptr,&descriptor_pool),"Vulkan reduction descriptor pool creation failed");
            VkDescriptorSetAllocateInfo set_info{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};set_info.descriptorPool = descriptor_pool;set_info.descriptorSetCount = 1;set_info.pSetLayouts = &descriptor_layout;
            check_vk(vkAllocateDescriptorSets(device_,&set_info,&descriptor_set),"Vulkan reduction descriptor allocation failed");
            VkDescriptorBufferInfo words_descriptor{field_buffer,0,bytes};
            VkDescriptorBufferInfo partials_descriptor{partials, 0, partial_bytes};
            VkWriteDescriptorSet writes[2]{};
            writes[0].dstSet = descriptor_set;writes[0].dstBinding = 0;writes[0].descriptorCount = 1;writes[0].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;writes[0].pBufferInfo = &words_descriptor;
            writes[1].dstSet = descriptor_set;writes[1].dstBinding = 1;writes[1].descriptorCount = 1;writes[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;writes[1].pBufferInfo = &partials_descriptor;
            vkUpdateDescriptorSets(device_, 2, writes, 0, nullptr);
            VkCommandBufferAllocateInfo command_allocation{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};command_allocation.commandPool = command_pool_;command_allocation.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;command_allocation.commandBufferCount = 1;
            check_vk(vkAllocateCommandBuffers(device_,&command_allocation,&command),"Vulkan command allocation failed");
            VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;check_vk(vkBeginCommandBuffer(command,&begin),"Vulkan command recording failed");
            VkMemoryBarrier before{VK_STRUCTURE_TYPE_MEMORY_BARRIER};before.srcAccessMask=VK_ACCESS_HOST_WRITE_BIT|VK_ACCESS_TRANSFER_WRITE_BIT|VK_ACCESS_SHADER_WRITE_BIT;before.dstAccessMask=VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT;
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_HOST_BIT|VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,1,&before,0,nullptr,0,nullptr);
            struct ReduceParameters { std::uint32_t offset; std::uint32_t count; } parameters{static_cast<std::uint32_t>(first_word), static_cast<std::uint32_t>(count)};
            vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline_layout, 0, 1, &descriptor_set, 0, nullptr);
            vkCmdPushConstants(command, pipeline_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(parameters), &parameters);
            vkCmdDispatch(command, groups, 1, 1);
            VkMemoryBarrier after{VK_STRUCTURE_TYPE_MEMORY_BARRIER};after.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;after.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
            vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &after, 0, nullptr, 0, nullptr);
            check_vk(vkEndCommandBuffer(command),"Vulkan command finalization failed");
            VkFenceCreateInfo fence_info{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};check_vk(vkCreateFence(device_,&fence_info,nullptr,&fence),"Vulkan fence creation failed");
            VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount = 1;submit.pCommandBuffers = &command;
            const auto submit_result=vkQueueSubmit(queue_,1,&submit,fence);
            if(submit_result==VK_ERROR_DEVICE_LOST) throw DeviceLost("Vulkan device was lost during reduction submission");
            if(submit_result!=VK_SUCCESS) throw GpuExecutionError("Vulkan reduction submission failed");
            wait_for_fence(fence);
            void* mapped=nullptr;check_vk(vkMapMemory(device_,partials_memory,0,partial_bytes,0,&mapped),"Vulkan reduction partial map failed");
            std::uint64_t sum = 0;
            const auto* entries = static_cast<const std::uint32_t*>(mapped);
            for (std::uint32_t group = 0; group < groups; ++group) {
                const std::uint64_t partial = (std::uint64_t(entries[group * 2U + 1U]) << 32U) | entries[group * 2U];
                if (sum > std::numeric_limits<std::uint64_t>::max() - partial) { vkUnmapMemory(device_, partials_memory); throw ProtocolError("Vulkan reduction partial fold overflows exact u64"); }
                sum += partial;
            }
            vkUnmapMemory(device_, partials_memory);
            cleanup();
            return {sum, count, "vulkan"};
        } catch(const DeviceLost&) {
            recover_after_device_loss([&cleanup]() noexcept { cleanup(); });
            return {sum_words(image.words,first_word,count),count,"native-cpu"};
        } catch(...) { cleanup(); throw; }
#endif
    }
#ifdef CASSIFI_HAVE_VULKAN
    struct ImageVersion {
        std::uint64_t generation{};
        std::uint64_t fence{};
        Digest profile{};
        Digest state{};
        Digest catalog{};
        Digest canonical{};
        std::array<std::uint32_t,8> shape{};
        std::uint32_t rank{};
        std::size_t word_count{};
        std::uint64_t host_mutation_generation{};
        bool canonical_digest_dirty{};
    };
    struct ResidentImage {
        VkBuffer buffer{VK_NULL_HANDLE};
        VkDeviceMemory memory{VK_NULL_HANDLE};
        VkDeviceSize bytes{};
        VkDeviceSize allocation_bytes{};
        ImageVersion version{};
        bool version_valid{};
    };
    struct OwnerImages {
        ResidentImage committed{};
        ResidentImage pending{};
        ImageVersion pending_base{};
        bool pending_valid{};
    };
    struct BufferResource {
        VkBuffer buffer{VK_NULL_HANDLE};
        VkDeviceMemory memory{VK_NULL_HANDLE};
        VkDeviceSize bytes{};
        VkDeviceSize allocation_bytes{};
        std::uint32_t memory_type_index{UINT32_MAX};
    };
    struct ComputeResources {
        VkShaderModule shader{VK_NULL_HANDLE};
        VkDescriptorSetLayout descriptor_layout{VK_NULL_HANDLE};
        VkPipelineLayout pipeline_layout{VK_NULL_HANDLE};
        VkPipeline pipeline{VK_NULL_HANDLE};
        VkDescriptorPool descriptor_pool{VK_NULL_HANDLE};
        VkDescriptorSet descriptor_set{VK_NULL_HANDLE};
    };
    struct GpuExecutionError : std::runtime_error { using std::runtime_error::runtime_error; };
    struct DeviceLost : GpuExecutionError { using GpuExecutionError::GpuExecutionError; };

    static bool parse_digest(std::string_view hex,Digest& digest) noexcept {
        if(hex.size()!=64U) return false;
        const auto nibble=[](char value)->int {
            if(value>='0'&&value<='9') return value-'0';
            if(value>='a'&&value<='f') return value-'a'+10;
            return -1;
        };
        for(std::size_t i=0;i<digest.size();++i){
            const auto high=nibble(hex[i*2U]);const auto low=nibble(hex[i*2U+1U]);
            if(high<0||low<0) return false;
            digest[i]=std::byte((high<<4)|low);
        }
        return true;
    }
    static ImageVersion version_for(const PackedImage& image) {
        ImageVersion version;
        if(!parse_digest(image.profile_sha256,version.profile)||
                !parse_digest(image.state_sha256,version.state)||
                !parse_digest(image.catalog_sha256,version.catalog))
            throw ProtocolError("field image identity digest is invalid");
        const auto count=checked_word_count(image.shape);
        if(count!=image.words.size()) throw ProtocolError("packed image shape is corrupt");
        version.generation=image.service_generation;version.fence=image.fence;
        if(!image.canonical_digest_dirty) version.canonical=image.canonical_bytes_sha256;
        version.rank=static_cast<std::uint32_t>(image.shape.size());version.word_count=image.words.size();
        version.host_mutation_generation=image.host_mutation_generation;
        version.canonical_digest_dirty=image.canonical_digest_dirty;
        std::copy(image.shape.begin(),image.shape.end(),version.shape.begin());
        return version;
    }
    static bool same_version(const ImageVersion& left,const ImageVersion& right) noexcept {
        return left.generation==right.generation&&left.fence==right.fence&&left.profile==right.profile&&
            left.state==right.state&&left.catalog==right.catalog&&left.canonical==right.canonical&&
            left.shape==right.shape&&left.rank==right.rank&&left.word_count==right.word_count&&
            left.host_mutation_generation==right.host_mutation_generation&&
            left.canonical_digest_dirty==right.canonical_digest_dirty;
    }
    static bool same_content(const ImageVersion& left,const ImageVersion& right) noexcept {
        return left.generation==right.generation&&left.profile==right.profile&&left.catalog==right.catalog&&
            left.canonical==right.canonical&&left.shape==right.shape&&left.rank==right.rank&&
            left.word_count==right.word_count&&left.host_mutation_generation==right.host_mutation_generation&&
            left.canonical_digest_dirty==right.canonical_digest_dirty;
    }
    static bool valid_successor(const PackedImage& predecessor,const PackedImage& accepted) {
        if(predecessor.owner_id!=accepted.owner_id||predecessor.service_generation!=accepted.service_generation||
                predecessor.fence==std::numeric_limits<std::uint64_t>::max()||
                accepted.fence!=predecessor.fence+1U) return false;
        const auto before=version_for(predecessor);const auto after=version_for(accepted);
        return before.profile==after.profile&&before.catalog==after.catalog&&before.shape==after.shape&&
            before.rank==after.rank&&before.word_count==after.word_count;
    }
    static void check_vk(VkResult result,const char* message) {
        if(result==VK_SUCCESS) return;
        if(result==VK_ERROR_DEVICE_LOST) throw DeviceLost(message);
        throw GpuExecutionError(message);
    }
    void release_buffer(BufferResource& resource) noexcept {
        if(resource.buffer!=VK_NULL_HANDLE) vkDestroyBuffer(device_,resource.buffer,nullptr);
        if(resource.memory!=VK_NULL_HANDLE) vkFreeMemory(device_,resource.memory,nullptr);
        resource={};
    }
    void release_image(ResidentImage& image) noexcept {
        if(image.buffer!=VK_NULL_HANDLE) vkDestroyBuffer(device_,image.buffer,nullptr);
        if(image.memory!=VK_NULL_HANDLE) vkFreeMemory(device_,image.memory,nullptr);
        image={};
    }
    void release_all_owner_images() noexcept {
        for(auto& [owner,images]:owner_images_){
            (void)owner;
            if(images.pending.buffer!=VK_NULL_HANDLE) gpu_field_retained_bytes_.fetch_sub(images.pending.allocation_bytes,std::memory_order_relaxed);
            if(images.committed.buffer!=VK_NULL_HANDLE) gpu_field_retained_bytes_.fetch_sub(images.committed.allocation_bytes,std::memory_order_relaxed);
            release_image(images.pending);release_image(images.committed);
        }
        owner_images_.clear();
        selected_memory_metadata_.store(UINT64_MAX,std::memory_order_release);
    }
    [[nodiscard]] std::uint64_t field_resident_bytes() const noexcept {
        return gpu_field_retained_bytes_.load(std::memory_order_relaxed);
    }
    [[nodiscard]] std::uint32_t choose_host_memory_type(std::uint32_t type_bits,VkDeviceSize required_bytes,
            const VkPhysicalDeviceMemoryProperties& properties) const noexcept {
        std::array<VkDeviceSize,VK_MAX_MEMORY_HEAPS> capacities{};
        for(std::uint32_t heap=0;heap<properties.memoryHeapCount;++heap)
            capacities[heap]=properties.memoryHeaps[heap].size;
#ifdef VK_EXT_MEMORY_BUDGET_EXTENSION_NAME
        if(budget_extension_&&memory_properties2_){
            VkPhysicalDeviceMemoryBudgetPropertiesEXT budget{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_BUDGET_PROPERTIES_EXT};
            VkPhysicalDeviceMemoryProperties2 memory_properties2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MEMORY_PROPERTIES_2};
            memory_properties2.pNext=&budget;memory_properties2_(physical_,&memory_properties2);
            for(std::uint32_t heap=0;heap<properties.memoryHeapCount;++heap){
                const auto available=budget.heapBudget[heap];
                const auto used=budget.heapUsage[heap];
                if(available||used) capacities[heap]=available>used?available-used:0U;
            }
        }
#endif
        std::uint32_t selected=UINT32_MAX;bool selected_device_local=false;
        for(std::uint32_t index=0;index<properties.memoryTypeCount;++index){
            if((type_bits&(1U<<index))==0) continue;
            const auto& type=properties.memoryTypes[index];
            const auto flags=type.propertyFlags;
            if((flags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))!=
                    (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) continue;
            if(type.heapIndex>=properties.memoryHeapCount||required_bytes>capacities[type.heapIndex]) continue;
            const bool device_local=(flags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)!=0&&
                (properties.memoryHeaps[type.heapIndex].flags&VK_MEMORY_HEAP_DEVICE_LOCAL_BIT)!=0;
            if(selected==UINT32_MAX||(device_local&&!selected_device_local)){
                selected=index;selected_device_local=device_local;
            }
        }
        return selected;
    }
    void remember_field_memory_type(std::uint32_t memory_type,const VkPhysicalDeviceMemoryProperties& properties) noexcept {
        const auto& type=properties.memoryTypes[memory_type];
        const auto selection=std::uint64_t(memory_type)|(std::uint64_t(type.heapIndex)<<8U)|
            (std::uint64_t(type.propertyFlags)<<16U);
        selected_memory_metadata_.store(selection,std::memory_order_release);
    }
    BufferResource create_host_buffer(VkDeviceSize bytes,VkBufferUsageFlags usage,const char* message) {
        BufferResource resource;resource.bytes=bytes;
        VkBufferCreateInfo info{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};info.size=bytes;info.usage=usage;info.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        check_vk(vkCreateBuffer(device_,&info,nullptr,&resource.buffer),message);
        try {
            VkMemoryRequirements requirements{};vkGetBufferMemoryRequirements(device_,resource.buffer,&requirements);
            if(requirements.size>VkDeviceSize(kMaxFieldBytes)) throw GpuExecutionError("Vulkan allocation exceeds the 64 MiB physical unit");
            resource.allocation_bytes=requirements.size;
            VkPhysicalDeviceMemoryProperties properties{};vkGetPhysicalDeviceMemoryProperties(physical_,&properties);
            const auto memory_type=choose_host_memory_type(requirements.memoryTypeBits,requirements.size,properties);
            if(memory_type==UINT32_MAX) throw GpuExecutionError("Vulkan device has no coherent host-visible field memory within heap capacity");
            resource.memory_type_index=memory_type;
            const auto field_usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT;
            VkMemoryAllocateInfo allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
            allocation.allocationSize=requirements.size;allocation.memoryTypeIndex=memory_type;
            check_vk(vkAllocateMemory(device_,&allocation,nullptr,&resource.memory),"Vulkan field memory allocation failed");
            check_vk(vkBindBufferMemory(device_,resource.buffer,resource.memory,0),"Vulkan field memory binding failed");
            if((usage&field_usage)==field_usage) remember_field_memory_type(memory_type,properties);
            return resource;
        } catch(...) {
            release_buffer(resource);
            throw;
        }
    }
    void create_compute_resources(ComputeResources& resources,std::span<const std::uint32_t> code,
            std::uint32_t descriptor_count,std::uint32_t push_bytes,const char* message) {
        try {
            VkShaderModuleCreateInfo shader_info{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
            shader_info.codeSize=code.size_bytes();shader_info.pCode=code.data();
            check_vk(vkCreateShaderModule(device_,&shader_info,nullptr,&resources.shader),message);
            std::array<VkDescriptorSetLayoutBinding,2> bindings{};
            for(std::uint32_t index=0;index<descriptor_count;++index){
                bindings[index].binding=index;bindings[index].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
                bindings[index].descriptorCount=1;bindings[index].stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;
            }
            VkDescriptorSetLayoutCreateInfo descriptor_info{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
            descriptor_info.bindingCount=descriptor_count;descriptor_info.pBindings=bindings.data();
            check_vk(vkCreateDescriptorSetLayout(device_,&descriptor_info,nullptr,&resources.descriptor_layout),message);
            VkPushConstantRange push{};push.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT;push.offset=0;push.size=push_bytes;
            VkPipelineLayoutCreateInfo layout_info{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
            layout_info.setLayoutCount=1;layout_info.pSetLayouts=&resources.descriptor_layout;
            layout_info.pushConstantRangeCount=1;layout_info.pPushConstantRanges=&push;
            check_vk(vkCreatePipelineLayout(device_,&layout_info,nullptr,&resources.pipeline_layout),message);
            VkPipelineShaderStageCreateInfo stage{VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};
            stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;stage.module=resources.shader;stage.pName="main";
            VkComputePipelineCreateInfo pipeline_info{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
            pipeline_info.stage=stage;pipeline_info.layout=resources.pipeline_layout;
            check_vk(vkCreateComputePipelines(device_,VK_NULL_HANDLE,1,&pipeline_info,nullptr,&resources.pipeline),message);
            VkDescriptorPoolSize pool_size{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,descriptor_count};
            VkDescriptorPoolCreateInfo pool_info{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
            pool_info.maxSets=1;pool_info.poolSizeCount=1;pool_info.pPoolSizes=&pool_size;
            check_vk(vkCreateDescriptorPool(device_,&pool_info,nullptr,&resources.descriptor_pool),message);
            VkDescriptorSetAllocateInfo set_info{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO};
            set_info.descriptorPool=resources.descriptor_pool;set_info.descriptorSetCount=1;set_info.pSetLayouts=&resources.descriptor_layout;
            check_vk(vkAllocateDescriptorSets(device_,&set_info,&resources.descriptor_set),message);
        } catch(...) {
            destroy_compute_resources(resources);
            throw;
        }
    }
    void destroy_compute_resources(ComputeResources& resources) noexcept {
        if(resources.descriptor_pool) vkDestroyDescriptorPool(device_,resources.descriptor_pool,nullptr);
        if(resources.pipeline) vkDestroyPipeline(device_,resources.pipeline,nullptr);
        if(resources.pipeline_layout) vkDestroyPipelineLayout(device_,resources.pipeline_layout,nullptr);
        if(resources.descriptor_layout) vkDestroyDescriptorSetLayout(device_,resources.descriptor_layout,nullptr);
        if(resources.shader) vkDestroyShaderModule(device_,resources.shader,nullptr);
        resources={};
    }
    [[nodiscard]] VkBuffer exact_owner_buffer(const PackedImage& image,const ImageVersion& version) const noexcept {
        if(image.canonical_digest_dirty) return VK_NULL_HANDLE;
        try {
            const auto found=owner_images_.find(image.owner_id);
            if(found==owner_images_.end()) return VK_NULL_HANDLE;
            const auto matches=[&](const ResidentImage& resident){
                return resident.buffer!=VK_NULL_HANDLE&&resident.version_valid&&same_version(resident.version,version);
            };
            if(matches(found->second.pending)) return found->second.pending.buffer;
            if(matches(found->second.committed)) return found->second.committed.buffer;
        } catch(...) {
        }
        return VK_NULL_HANDLE;
    }
    void wait_for_fence(VkFence fence) {
        const auto result=vkWaitForFences(device_,1,&fence,VK_TRUE,5'000'000'000ULL);
        if(result==VK_SUCCESS) return;
        if(result==VK_ERROR_DEVICE_LOST) throw DeviceLost("Vulkan field operation lost its device");
        const auto idle=vkDeviceWaitIdle(device_);
        if(idle==VK_ERROR_DEVICE_LOST) throw DeviceLost("Vulkan device was lost while retiring a field operation");
        if(idle!=VK_SUCCESS) throw DeviceLost("Vulkan device could not safely retire a field operation");
        if(result==VK_TIMEOUT) throw GpuExecutionError("Vulkan field operation timed out");
        throw GpuExecutionError("Vulkan field operation fence wait failed");
    }
    bool apply_gpu_candidate(PackedImage& image,std::span<const WordOperation> operations) {
        const auto changed_pages=validate_word_operations(image.words,operations);
        if(checked_word_count(image.shape)!=image.words.size()) throw ProtocolError("packed image shape is corrupt");
        const auto page_count=std::max<std::size_t>(1U,(image.words.size()*sizeof(std::uint32_t)+kPageBytes-1U)/kPageBytes);
        if(image.page_sha256.size()!=page_count) throw ProtocolError("candidate page manifest is corrupt");
        if(std::none_of(changed_pages.begin(),changed_pages.end(),[](auto page){return page!=0;})) return true;
        const auto input_version=version_for(image);
        auto [owner_it,inserted]=owner_images_.try_emplace(image.owner_id);
        auto& owner=owner_it->second;
        const ResidentImage* source=nullptr;
        ImageVersion base_version=input_version;
        if(owner.pending_valid){
            if(!same_version(owner.pending.version,input_version))
                throw ProtocolError("candidate image does not match its pending Vulkan successor");
            source=&owner.pending;base_version=owner.pending_base;
        }else if(owner.committed.buffer!=VK_NULL_HANDLE&&owner.committed.version_valid&&
                same_version(owner.committed.version,input_version)){
            source=&owner.committed;
        }

        const VkDeviceSize bytes=static_cast<VkDeviceSize>(image.packed_bytes());
        const auto usages=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        BufferResource candidate_buffer{},scratch{},compare_status{};
        ComputeResources add_compute{},compare_compute{};
        VkCommandBuffer command=VK_NULL_HANDLE;VkFence fence=VK_NULL_HANDLE;
        VkDeviceMemory mapped_candidate_memory=VK_NULL_HANDLE;
        bool candidate_published=false;
        ResidentImage next_candidate{};
        const auto cleanup=[&]() noexcept {
            if(mapped_candidate_memory!=VK_NULL_HANDLE){
                vkUnmapMemory(device_,mapped_candidate_memory);mapped_candidate_memory=VK_NULL_HANDLE;
            }
            if(fence) vkDestroyFence(device_,fence,nullptr);
            if(command) vkFreeCommandBuffers(device_,command_pool_,1,&command);
            destroy_compute_resources(add_compute);destroy_compute_resources(compare_compute);
            release_buffer(scratch);release_buffer(compare_status);
            if(!candidate_published) release_buffer(candidate_buffer);
        };
        try {
            candidate_buffer=create_host_buffer(bytes,usages,"Vulkan candidate field buffer allocation failed");
            std::uint64_t max_overlap_bytes=0;
            bool has_add=false,has_compare=false;
            for(const auto& operation:operations){
                if(operation.opcode==WordOpcode::add_constant&&operation.count_or_value) has_add=true;
                if(operation.opcode==WordOpcode::compare_set) has_compare=true;
                if(operation.opcode==WordOpcode::copy&&operation.count_or_value){
                    const auto source_first=operation.source_or_expected;
                    const auto destination_first=operation.destination;
                    const auto count=std::uint64_t(operation.count_or_value);
                    if(source_first<destination_first+count&&destination_first<source_first+count)
                        max_overlap_bytes=std::max(max_overlap_bytes,count*sizeof(std::uint32_t));
                }
            }
            if(max_overlap_bytes) scratch=create_host_buffer(max_overlap_bytes,VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT,"Vulkan overlapping-copy scratch allocation failed");
            if(has_compare) compare_status=create_host_buffer(sizeof(std::uint32_t),VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,"Vulkan compare-set status allocation failed");
            if(has_add) create_compute_resources(add_compute,kAddConstantShader,1,3U*sizeof(std::uint32_t),"Vulkan add-constant pipeline creation failed");
            if(has_compare) create_compute_resources(compare_compute,kCompareSetShader,2,3U*sizeof(std::uint32_t),"Vulkan compare-set pipeline creation failed");
            if(has_add){
                VkDescriptorBufferInfo buffer_info{candidate_buffer.buffer,0,bytes};
                VkWriteDescriptorSet write{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
                write.dstSet=add_compute.descriptor_set;write.dstBinding=0;write.descriptorCount=1;
                write.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;write.pBufferInfo=&buffer_info;
                vkUpdateDescriptorSets(device_,1,&write,0,nullptr);
            }
            if(has_compare){
                VkDescriptorBufferInfo infos[2]{{candidate_buffer.buffer,0,bytes},{compare_status.buffer,0,sizeof(std::uint32_t)}};
                VkWriteDescriptorSet writes[2]{};
                for(std::uint32_t index=0;index<2;++index){
                    writes[index].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;writes[index].dstSet=compare_compute.descriptor_set;
                    writes[index].dstBinding=index;writes[index].descriptorCount=1;
                    writes[index].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;writes[index].pBufferInfo=&infos[index];
                }
                vkUpdateDescriptorSets(device_,2,writes,0,nullptr);
                void* mapped_status=nullptr;
                check_vk(vkMapMemory(device_,compare_status.memory,0,sizeof(std::uint32_t),0,&mapped_status),"Vulkan compare-set status map failed");
                const std::uint32_t zero=0;std::memcpy(mapped_status,&zero,sizeof(zero));vkUnmapMemory(device_,compare_status.memory);
            }
            if(!source){
                void* mapped=nullptr;check_vk(vkMapMemory(device_,candidate_buffer.memory,0,bytes,0,&mapped),"Vulkan candidate host upload map failed");
                std::memcpy(mapped,image.words.data(),static_cast<std::size_t>(bytes));vkUnmapMemory(device_,candidate_buffer.memory);
                gpu_field_host_upload_bytes_.fetch_add(bytes,std::memory_order_relaxed);
            }
            VkCommandBufferAllocateInfo command_info{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
            command_info.commandPool=command_pool_;command_info.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;command_info.commandBufferCount=1;
            check_vk(vkAllocateCommandBuffers(device_,&command_info,&command),"Vulkan field command allocation failed");
            VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
            check_vk(vkBeginCommandBuffer(command,&begin),"Vulkan field command recording failed");
            bool writes_pending=!source;
            if(source){
                VkBufferCopy clone{0,0,bytes};vkCmdCopyBuffer(command,source->buffer,candidate_buffer.buffer,1,&clone);writes_pending=true;
            }
            const auto barrier_writes=[&](){
                VkMemoryBarrier barrier{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
                barrier.srcAccessMask=VK_ACCESS_HOST_WRITE_BIT|VK_ACCESS_TRANSFER_WRITE_BIT|VK_ACCESS_SHADER_WRITE_BIT;
                barrier.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT|VK_ACCESS_TRANSFER_WRITE_BIT|VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT;
                vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_HOST_BIT|VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                    VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,0,1,&barrier,0,nullptr,0,nullptr);
            };
            VkPhysicalDeviceProperties properties{};vkGetPhysicalDeviceProperties(physical_,&properties);
            const std::uint64_t max_add_invocations=std::uint64_t(std::max(1U,properties.limits.maxComputeWorkGroupCount[0]))*256U;
            for(const auto& operation:operations){
                if(writes_pending){barrier_writes();writes_pending=false;}
                switch(operation.opcode){
                case WordOpcode::set:
                    vkCmdFillBuffer(command,candidate_buffer.buffer,VkDeviceSize(operation.destination)*4U,4U,operation.count_or_value);
                    writes_pending=true;break;
                case WordOpcode::fill:
                    if(operation.count_or_value){
                        vkCmdFillBuffer(command,candidate_buffer.buffer,VkDeviceSize(operation.destination)*4U,
                            VkDeviceSize(operation.count_or_value)*4U,operation.value);writes_pending=true;
                    }
                    break;
                case WordOpcode::copy:
                    if(operation.count_or_value){
                        const auto source_first=operation.source_or_expected;const auto destination_first=operation.destination;
                        const auto count=std::uint64_t(operation.count_or_value);
                        const bool overlaps=source_first<destination_first+count&&destination_first<source_first+count;
                        if(overlaps){
                            VkBufferCopy to_scratch{VkDeviceSize(source_first)*4U,0,VkDeviceSize(count)*4U};
                            vkCmdCopyBuffer(command,candidate_buffer.buffer,scratch.buffer,1,&to_scratch);
                            VkMemoryBarrier scratch_barrier{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
                            scratch_barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;scratch_barrier.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;
                            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,1,&scratch_barrier,0,nullptr,0,nullptr);
                            VkBufferCopy from_scratch{0,VkDeviceSize(destination_first)*4U,VkDeviceSize(count)*4U};
                            vkCmdCopyBuffer(command,scratch.buffer,candidate_buffer.buffer,1,&from_scratch);
                        }else{
                            VkBufferCopy region{VkDeviceSize(source_first)*4U,VkDeviceSize(destination_first)*4U,VkDeviceSize(count)*4U};
                            vkCmdCopyBuffer(command,candidate_buffer.buffer,candidate_buffer.buffer,1,&region);
                        }
                        writes_pending=true;
                    }
                    break;
                case WordOpcode::compare_set:{
                    struct Parameters{std::uint32_t destination,expected,value;} parameters{
                        static_cast<std::uint32_t>(operation.destination),static_cast<std::uint32_t>(operation.source_or_expected),operation.count_or_value};
                    vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_COMPUTE,compare_compute.pipeline);
                    vkCmdBindDescriptorSets(command,VK_PIPELINE_BIND_POINT_COMPUTE,compare_compute.pipeline_layout,0,1,&compare_compute.descriptor_set,0,nullptr);
                    vkCmdPushConstants(command,compare_compute.pipeline_layout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(parameters),&parameters);
                    vkCmdDispatch(command,1,1,1);writes_pending=true;break;
                }
                case WordOpcode::add_constant:{
                    std::uint64_t completed=0;
                    while(completed<operation.count_or_value){
                        const auto chunk=static_cast<std::uint32_t>(std::min<std::uint64_t>(operation.count_or_value-completed,max_add_invocations));
                        struct Parameters{std::uint32_t offset,count,value;} parameters{
                            static_cast<std::uint32_t>(operation.destination+completed),chunk,operation.value};
                        vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_COMPUTE,add_compute.pipeline);
                        vkCmdBindDescriptorSets(command,VK_PIPELINE_BIND_POINT_COMPUTE,add_compute.pipeline_layout,0,1,&add_compute.descriptor_set,0,nullptr);
                        vkCmdPushConstants(command,add_compute.pipeline_layout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(parameters),&parameters);
                        vkCmdDispatch(command,static_cast<std::uint32_t>((std::uint64_t(chunk)+255U)/256U),1,1);
                        completed+=chunk;writes_pending=true;
                    }
                    break;
                }
                default: throw ProtocolError("word operation opcode is unsupported");
                }
            }
            if(writes_pending) barrier_writes();
            if(has_compare){
                VkMemoryBarrier status_barrier{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
                status_barrier.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;status_barrier.dstAccessMask=VK_ACCESS_HOST_READ_BIT;
                vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&status_barrier,0,nullptr,0,nullptr);
            }
            VkMemoryBarrier host_barrier{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
            host_barrier.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT|VK_ACCESS_SHADER_WRITE_BIT;
            host_barrier.dstAccessMask=VK_ACCESS_HOST_READ_BIT;
            vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                VK_PIPELINE_STAGE_HOST_BIT,0,1,&host_barrier,0,nullptr,0,nullptr);
            check_vk(vkEndCommandBuffer(command),"Vulkan field command finalization failed");
            VkFenceCreateInfo fence_info{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
            check_vk(vkCreateFence(device_,&fence_info,nullptr,&fence),"Vulkan field fence creation failed");
            VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&command;
            check_vk(vkQueueSubmit(queue_,1,&submit,fence),"Vulkan field submission failed");
            wait_for_fence(fence);

            if(has_compare){
                void* mapped_status=nullptr;check_vk(vkMapMemory(device_,compare_status.memory,0,sizeof(std::uint32_t),0,&mapped_status),"Vulkan compare-set status read failed");
                const auto stale=*static_cast<const std::uint32_t*>(mapped_status)!=0;vkUnmapMemory(device_,compare_status.memory);
                if(stale) throw ProtocolError("word compare-set precondition is stale");
            }
            auto next_pages=image.page_sha256;
            void* mapped=nullptr;
            check_vk(vkMapMemory(device_,candidate_buffer.memory,0,bytes,0,&mapped),"Vulkan field result map failed");
            mapped_candidate_memory=candidate_buffer.memory;
            const auto* result_words=static_cast<const std::uint32_t*>(mapped);
            constexpr std::size_t page_words=kPageBytes/sizeof(std::uint32_t);
            std::uint64_t exported_bytes=0;
            for(std::size_t page=0;page<changed_pages.size();++page){
                if(!changed_pages[page]) continue;
                const auto first=page*page_words;const auto count=std::min(page_words,image.words.size()-first);
                const auto page_span=std::span<const std::uint32_t>(result_words+first,count);
                next_pages[page]=sha256(std::as_bytes(page_span));
                exported_bytes+=count*sizeof(std::uint32_t);
            }
            if(std::any_of(changed_pages.begin(),changed_pages.end(),[](std::uint8_t changed){return changed!=0;}))
                mark_host_mutated(image);
            for(std::size_t page=0;page<changed_pages.size();++page){
                if(!changed_pages[page]) continue;
                const auto first=page*page_words;const auto count=std::min(page_words,image.words.size()-first);
                std::memcpy(image.words.data()+first,result_words+first,count*sizeof(std::uint32_t));
            }
            vkUnmapMemory(device_,candidate_buffer.memory);mapped_candidate_memory=VK_NULL_HANDLE;
            image.page_sha256=std::move(next_pages);
            image.canonical_bytes_sha256=canonical_image_digest(image.words);
            image.canonical_digest_dirty=false;
            next_candidate.buffer=candidate_buffer.buffer;next_candidate.memory=candidate_buffer.memory;
            next_candidate.bytes=bytes;next_candidate.allocation_bytes=candidate_buffer.allocation_bytes;
            next_candidate.version=version_for(image);next_candidate.version_valid=true;
            candidate_buffer={};candidate_published=true;
            auto old_pending=std::move(owner.pending);
            const auto old_pending_bytes=old_pending.buffer==VK_NULL_HANDLE?0U:old_pending.allocation_bytes;
            owner.pending=std::move(next_candidate);owner.pending_base=base_version;owner.pending_valid=true;
            if(old_pending_bytes) gpu_field_retained_bytes_.fetch_sub(old_pending_bytes,std::memory_order_relaxed);
            gpu_field_retained_bytes_.fetch_add(owner.pending.allocation_bytes,std::memory_order_relaxed);
            release_image(old_pending);
            gpu_field_batches_.fetch_add(1U,std::memory_order_relaxed);
            gpu_field_changed_page_export_bytes_.fetch_add(exported_bytes,std::memory_order_relaxed);
            cleanup();
            return true;
        } catch(...) {
            cleanup();
            if(inserted&&owner.pending.buffer==VK_NULL_HANDLE&&owner.committed.buffer==VK_NULL_HANDLE)
                owner_images_.erase(owner_it);
            throw;
        }
    }

    template<class RetireLocal>
    void recover_after_device_loss(RetireLocal&& retire_local) noexcept {
        available_=false;reason_="Vulkan device lost; rebuilding from canonical host backing";
        if(device_!=VK_NULL_HANDLE) (void)vkDeviceWaitIdle(device_);
        retire_local();
        if(device_!=VK_NULL_HANDLE){
            release_resident();release_all_owner_images();
            if(command_pool_!=VK_NULL_HANDLE) vkDestroyCommandPool(device_,command_pool_,nullptr);
            command_pool_=VK_NULL_HANDLE;
            vkDestroyDevice(device_,nullptr);device_=VK_NULL_HANDLE;queue_=VK_NULL_HANDLE;
        }
        const float priority=1.0F;
        VkDeviceQueueCreateInfo queue_info{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
        queue_info.queueFamilyIndex=queue_family_;queue_info.queueCount=1;queue_info.pQueuePriorities=&priority;
        VkDeviceCreateInfo device_info{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
        device_info.queueCreateInfoCount=1;device_info.pQueueCreateInfos=&queue_info;device_info.pEnabledFeatures=nullptr;
#ifdef VK_EXT_MEMORY_BUDGET_EXTENSION_NAME
        const char* device_extensions[]={VK_EXT_MEMORY_BUDGET_EXTENSION_NAME};
        if(budget_extension_){device_info.enabledExtensionCount=1;device_info.ppEnabledExtensionNames=device_extensions;}
#endif
        if(vkCreateDevice(physical_,&device_info,nullptr,&device_)!=VK_SUCCESS){
            reason_="Vulkan device recreation failed after device loss";return;
        }
        vkGetDeviceQueue(device_,queue_family_,0,&queue_);
        VkCommandPoolCreateInfo pool_info{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
        pool_info.flags=VK_COMMAND_POOL_CREATE_TRANSIENT_BIT|VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        pool_info.queueFamilyIndex=queue_family_;
        if(vkCreateCommandPool(device_,&pool_info,nullptr,&command_pool_)!=VK_SUCCESS){
            vkDestroyDevice(device_,nullptr);device_=VK_NULL_HANDLE;queue_=VK_NULL_HANDLE;
            reason_="Vulkan command pool recreation failed after device loss";return;
        }
        available_=true;reason_="recovered after device loss; canonical host backing will be uploaded on demand";
    }
    void recover_after_device_loss() noexcept {
        recover_after_device_loss([]() noexcept {});
    }
    ResidentImage resident_{};
    void ensure_resident(const PackedImage& image,const ImageVersion& version,VkDeviceSize bytes) {
        const bool reuse_allowed=!(image.canonical_digest_dirty&&image.host_mutation_generation==std::numeric_limits<std::uint64_t>::max());
        if(reuse_allowed&&resident_.buffer!=VK_NULL_HANDLE&&resident_.version_valid&&resident_.bytes==bytes&&
                same_version(resident_.version,version)) return;
        VkBuffer buffer = VK_NULL_HANDLE;
        VkDeviceMemory memory = VK_NULL_HANDLE;
        try {
            VkBufferCreateInfo info{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
            info.size = bytes;
            info.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
            info.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
            if (vkCreateBuffer(device_, &info, nullptr, &buffer) != VK_SUCCESS) {
                throw ProtocolError("Vulkan reduction resident buffer allocation failed");
            }
            VkMemoryRequirements requirements{};
            vkGetBufferMemoryRequirements(device_, buffer, &requirements);
            if (requirements.size > VkDeviceSize(kMaxFieldBytes)) {
                throw ProtocolError("Vulkan resident memory exceeds physical unit");
            }
            VkPhysicalDeviceMemoryProperties properties{};
            vkGetPhysicalDeviceMemoryProperties(physical_, &properties);
            const auto type=choose_host_memory_type(requirements.memoryTypeBits,requirements.size,properties);
            if(type==UINT32_MAX) throw ProtocolError("Vulkan resident image has no coherent host-visible memory within heap capacity");
            VkMemoryAllocateInfo allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
            allocation.allocationSize = requirements.size;
            allocation.memoryTypeIndex = type;
            if (vkAllocateMemory(device_, &allocation, nullptr, &memory) != VK_SUCCESS ||
                    vkBindBufferMemory(device_, buffer, memory, 0) != VK_SUCCESS) {
                throw ProtocolError("Vulkan reduction resident memory allocation failed");
            }
            void* mapped = nullptr;
            if (vkMapMemory(device_, memory, 0, bytes, 0, &mapped) != VK_SUCCESS) {
                throw ProtocolError("Vulkan reduction resident memory map failed");
            }
            std::memcpy(mapped, image.words.data(), static_cast<std::size_t>(bytes));
            vkUnmapMemory(device_, memory);
            release_resident();
            resident_.buffer = buffer;
            resident_.memory = memory;
            resident_.bytes = bytes;
            resident_.allocation_bytes = requirements.size;
            resident_.version=version;
            resident_.version_valid=true;
            remember_field_memory_type(type,properties);
            gpu_field_retained_bytes_.fetch_add(resident_.allocation_bytes,std::memory_order_relaxed);
            gpu_field_host_upload_bytes_.fetch_add(static_cast<std::uint64_t>(bytes),std::memory_order_relaxed);
        } catch (...) {
            if (buffer != VK_NULL_HANDLE) vkDestroyBuffer(device_, buffer, nullptr);
            if (memory != VK_NULL_HANDLE) vkFreeMemory(device_, memory, nullptr);
            throw;
        }
    }
    void release_resident() noexcept {
        if(resident_.buffer!=VK_NULL_HANDLE)
            gpu_field_retained_bytes_.fetch_sub(resident_.allocation_bytes,std::memory_order_relaxed);
        release_image(resident_);
    }
#else
    [[nodiscard]] std::uint64_t field_resident_bytes() const noexcept { return 0; }
#endif
private:
    std::atomic<bool> available_{false};std::string reason_{};std::string device_name_{};
    std::uint32_t device_index_{};std::string device_identity_{};std::string identity_kind_{};std::uint32_t vendor_id_{};std::uint32_t device_id_{};std::uint32_t driver_version_{};bool heaps_available_{false};
    std::atomic<std::uint64_t> gpu_field_batches_{};
    std::atomic<std::uint64_t> gpu_field_host_upload_bytes_{};
    std::atomic<std::uint64_t> gpu_field_changed_page_export_bytes_{};
    std::atomic<std::uint64_t> gpu_field_retained_bytes_{};
#ifdef CASSIFI_HAVE_VULKAN
    std::atomic<std::uint64_t> selected_memory_metadata_{UINT64_MAX};
    std::unordered_map<std::string,OwnerImages> owner_images_{};
    VkInstance instance_{VK_NULL_HANDLE};VkPhysicalDevice physical_{VK_NULL_HANDLE};VkDevice device_{VK_NULL_HANDLE};VkQueue queue_{VK_NULL_HANDLE};VkCommandPool command_pool_{VK_NULL_HANDLE};std::uint32_t queue_family_{};bool budget_extension_{false};PFN_vkGetPhysicalDeviceProperties2KHR properties2_{nullptr};PFN_vkGetPhysicalDeviceMemoryProperties2KHR memory_properties2_{nullptr};
#endif
};

} // namespace cassifi::field_runtime
