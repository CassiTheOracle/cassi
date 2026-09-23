#pragma once

#include "field_image.hpp"

#include <cstdint>
#include <memory>
#include <span>
#include <string>
#include <vector>

#ifdef CASSIFI_HAVE_VULKAN
#include <vulkan/vulkan.h>
#endif

namespace cassifi::field_runtime {

class VulkanBackend {
public:
    explicit VulkanBackend(std::uint32_t device_index = 0) {
#ifdef CASSIFI_HAVE_VULKAN
        VkApplicationInfo application{VK_STRUCTURE_TYPE_APPLICATION_INFO};
        application.pApplicationName = "CassiFI field-runtime";
        application.applicationVersion = VK_MAKE_VERSION(1,0,0);
        application.pEngineName = "CassiFI";
        application.engineVersion = VK_MAKE_VERSION(1,0,0);
        application.apiVersion = VK_API_VERSION_1_2;
        VkInstanceCreateInfo instance_info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
        instance_info.pApplicationInfo = &application;
        if (vkCreateInstance(&instance_info, nullptr, &instance_) != VK_SUCCESS) { reason_="vkCreateInstance failed"; return; }
        std::uint32_t count=0;
        if(vkEnumeratePhysicalDevices(instance_,&count,nullptr)!=VK_SUCCESS||!count){reason_="no Vulkan physical device";return;}
        std::vector<VkPhysicalDevice> devices(count);
        if(vkEnumeratePhysicalDevices(instance_,&count,devices.data())!=VK_SUCCESS||device_index>=count){reason_="Vulkan device index is unavailable";return;}
        physical_=devices[device_index];
        VkPhysicalDeviceProperties properties{}; vkGetPhysicalDeviceProperties(physical_,&properties); device_name_=properties.deviceName;
        VkPhysicalDeviceFeatures features{}; vkGetPhysicalDeviceFeatures(physical_,&features);
        if(!features.shaderFloat64){reason_="selected Vulkan device lacks shaderFloat64";return;}
        std::uint32_t queue_count=0; vkGetPhysicalDeviceQueueFamilyProperties(physical_,&queue_count,nullptr);
        std::vector<VkQueueFamilyProperties> queues(queue_count); vkGetPhysicalDeviceQueueFamilyProperties(physical_,&queue_count,queues.data());
        bool found=false; for(std::uint32_t i=0;i<queue_count;++i) if(queues[i].queueFlags&VK_QUEUE_COMPUTE_BIT){queue_family_=i;found=true;break;}
        if(!found){reason_="selected Vulkan device has no compute queue";return;}
        const float priority=1.0F; VkDeviceQueueCreateInfo queue_info{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO}; queue_info.queueFamilyIndex=queue_family_;queue_info.queueCount=1;queue_info.pQueuePriorities=&priority;
        VkPhysicalDeviceFeatures enabled{};enabled.shaderFloat64=VK_TRUE;
        VkDeviceCreateInfo device_info{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};device_info.queueCreateInfoCount=1;device_info.pQueueCreateInfos=&queue_info;device_info.pEnabledFeatures=&enabled;
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
        if(command_pool_!=VK_NULL_HANDLE) vkDestroyCommandPool(device_,command_pool_,nullptr);
        if(device_!=VK_NULL_HANDLE) vkDestroyDevice(device_,nullptr);
        if(instance_!=VK_NULL_HANDLE) vkDestroyInstance(instance_,nullptr);
#endif
    }
    [[nodiscard]] bool available() const noexcept{return available_;}
    [[nodiscard]] const std::string& reason() const noexcept{return reason_;}
    [[nodiscard]] const std::string& device_name() const noexcept{return device_name_;}

    void apply(PackedImage& image,std::span<const WordOperation> operations){
#ifndef CASSIFI_HAVE_VULKAN
        (void)image;(void)operations;throw ProtocolError("vulkan-unavailable: "+reason_);
#else
        if(!available_) throw ProtocolError("vulkan-unavailable: "+reason_);
        if(operations.size()>kMaxWordOperations) throw ProtocolError("Vulkan operation group exceeds its bound");
        // Validate every operation and compare-set before submitting any device work.
        auto expected=image.words;
        apply_word_operations(image,operations);
        const auto final_words=image.words;
        image.words=std::move(expected);
        const VkDeviceSize bytes=VkDeviceSize(image.packed_bytes());
        VkBuffer buffer=VK_NULL_HANDLE;VkDeviceMemory memory=VK_NULL_HANDLE;VkCommandBuffer command=VK_NULL_HANDLE;VkFence fence=VK_NULL_HANDLE;
        auto cleanup=[&](){if(fence)vkDestroyFence(device_,fence,nullptr);if(command)vkFreeCommandBuffers(device_,command_pool_,1,&command);if(buffer)vkDestroyBuffer(device_,buffer,nullptr);if(memory)vkFreeMemory(device_,memory,nullptr);};
        try{
            VkBufferCreateInfo buffer_info{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};buffer_info.size=bytes;buffer_info.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT;buffer_info.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
            if(vkCreateBuffer(device_,&buffer_info,nullptr,&buffer)!=VK_SUCCESS) throw ProtocolError("Vulkan candidate buffer allocation failed");
            VkMemoryRequirements requirements{};vkGetBufferMemoryRequirements(device_,buffer,&requirements);
            VkPhysicalDeviceMemoryProperties memory_properties{};vkGetPhysicalDeviceMemoryProperties(physical_,&memory_properties);
            std::uint32_t memory_type=UINT32_MAX;
            for(std::uint32_t i=0;i<memory_properties.memoryTypeCount;++i) if((requirements.memoryTypeBits&(1U<<i))&&(memory_properties.memoryTypes[i].propertyFlags&(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))==(VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)){memory_type=i;break;}
            if(memory_type==UINT32_MAX) throw ProtocolError("Vulkan device has no coherent host-visible candidate memory");
            VkMemoryAllocateInfo allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};allocation.allocationSize=requirements.size;allocation.memoryTypeIndex=memory_type;
            if(vkAllocateMemory(device_,&allocation,nullptr,&memory)!=VK_SUCCESS||vkBindBufferMemory(device_,buffer,memory,0)!=VK_SUCCESS) throw ProtocolError("Vulkan candidate memory allocation failed");
            void* mapped=nullptr;if(vkMapMemory(device_,memory,0,bytes,0,&mapped)!=VK_SUCCESS) throw ProtocolError("Vulkan candidate map failed");std::memcpy(mapped,image.words.data(),static_cast<std::size_t>(bytes));vkUnmapMemory(device_,memory);
            VkCommandBufferAllocateInfo command_allocation{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};command_allocation.commandPool=command_pool_;command_allocation.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;command_allocation.commandBufferCount=1;
            if(vkAllocateCommandBuffers(device_,&command_allocation,&command)!=VK_SUCCESS) throw ProtocolError("Vulkan command allocation failed");
            VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;if(vkBeginCommandBuffer(command,&begin)!=VK_SUCCESS) throw ProtocolError("Vulkan command recording failed");
            for(const auto& operation:operations){
                if(operation.opcode==WordOpcode::set){
                    vkCmdFillBuffer(command,buffer,VkDeviceSize(operation.destination)*4U,4U,operation.count_or_value);
                }else if(operation.opcode==WordOpcode::fill){
                    if(operation.count_or_value) vkCmdFillBuffer(command,buffer,VkDeviceSize(operation.destination)*4U,VkDeviceSize(operation.count_or_value)*4U,operation.value);
                }else if(operation.opcode==WordOpcode::compare_set){
                    vkCmdFillBuffer(command,buffer,VkDeviceSize(operation.destination)*4U,4U,operation.count_or_value);
                }else if(operation.opcode==WordOpcode::copy&&operation.count_or_value){
                    const auto source=operation.source_or_expected;
                    const auto destination=operation.destination;
                    const auto count=std::uint64_t(operation.count_or_value);
                    if(source<destination+count&&destination<source+count) throw ProtocolError("overlapping copy is not a compatible Vulkan operation group");
                    VkBufferCopy region{VkDeviceSize(source)*4U,VkDeviceSize(destination)*4U,VkDeviceSize(count)*4U};
                    vkCmdCopyBuffer(command,buffer,buffer,1,&region);
                }
            }
            if(vkEndCommandBuffer(command)!=VK_SUCCESS) throw ProtocolError("Vulkan command finalization failed");
            VkFenceCreateInfo fence_info{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};if(vkCreateFence(device_,&fence_info,nullptr,&fence)!=VK_SUCCESS) throw ProtocolError("Vulkan fence creation failed");
            VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&command;if(vkQueueSubmit(queue_,1,&submit,fence)!=VK_SUCCESS||vkWaitForFences(device_,1,&fence,VK_TRUE,5'000'000'000ULL)!=VK_SUCCESS) throw ProtocolError("Vulkan operation group failed or timed out");
            void* completed=nullptr;if(vkMapMemory(device_,memory,0,bytes,0,&completed)!=VK_SUCCESS) throw ProtocolError("Vulkan result map failed");
            std::vector<std::uint32_t> device_words(image.words.size());std::memcpy(device_words.data(),completed,static_cast<std::size_t>(bytes));vkUnmapMemory(device_,memory);
            if(device_words!=final_words) throw ProtocolError("Vulkan operation group disagrees with exact CPU contract");
            // Commit only after the bounded device result matches the CPU oracle.
            image.words=final_words;image.page_sha256=page_manifest(image.words);image.canonical_bytes_sha256=sha256(unpack_image(image));
            cleanup();
        }catch(...){cleanup();throw;}
#endif
    }
private:
    bool available_{false};std::string reason_{};std::string device_name_{};
#ifdef CASSIFI_HAVE_VULKAN
    VkInstance instance_{VK_NULL_HANDLE};VkPhysicalDevice physical_{VK_NULL_HANDLE};VkDevice device_{VK_NULL_HANDLE};VkQueue queue_{VK_NULL_HANDLE};VkCommandPool command_pool_{VK_NULL_HANDLE};std::uint32_t queue_family_{};
#endif
};

} // namespace cassifi::field_runtime
