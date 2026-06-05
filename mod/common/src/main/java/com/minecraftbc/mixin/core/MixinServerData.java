package com.minecraftbc.mixin.core;

import com.minecraftbc.core.MinecraftBC;
import net.minecraft.client.multiplayer.ServerData;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * ServerData Mixin
 * 
 * 扩展ServerData以支持P2P服务器标记。
 * 允许我们在服务器列表中存储额外的P2P信息。
 */
@Mixin(ServerData.class)
public class MixinServerData {
    
    @Unique
    private boolean minecraftbc$isP2PServer = false;
    
    @Unique
    private String minecraftbc$p2pServerId = null;
    
    @Unique
    private String minecraftbc$originalHost = null;
    
    @Unique
    private int minecraftbc$originalPort = 25565;
    
    /**
     * 检查是否是P2P服务器
     */
    @Unique
    public boolean minecraftbc$isP2PServer() {
        return minecraftbc$isP2PServer;
    }
    
    /**
     * 设置P2P服务器标记
     */
    @Unique
    public void minecraftbc$setP2PServer(boolean isP2P) {
        this.minecraftbc$isP2PServer = isP2P;
    }
    
    /**
     * 获取P2P服务器ID
     */
    @Unique
    public String minecraftbc$getP2PServerId() {
        return minecraftbc$p2pServerId;
    }
    
    /**
     * 设置P2P服务器ID
     */
    @Unique
    public void minecraftbc$setP2PServerId(String serverId) {
        this.minecraftbc$p2pServerId = serverId;
    }
    
    /**
     * 获取原始主机地址
     */
    @Unique
    public String minecraftbc$getOriginalHost() {
        return minecraftbc$originalHost;
    }
    
    /**
     * 设置原始主机地址
     */
    @Unique
    public void minecraftbc$setOriginalHost(String host) {
        this.minecraftbc$originalHost = host;
    }
    
    /**
     * 获取原始端口
     */
    @Unique
    public int minecraftbc$getOriginalPort() {
        return minecraftbc$originalPort;
    }
    
    /**
     * 设置原始端口
     */
    @Unique
    public void minecraftbc$setOriginalPort(int port) {
        this.minecraftbc$originalPort = port;
    }
    
    /**
     * 在复制服务器数据时复制P2P信息
     */
    @Inject(method = "copy", at = @At("RETURN"))
    private void onCopy(CallbackInfoReturnable<ServerData> cir) {
        ServerData copy = cir.getReturnValue();
        if (copy instanceof MixinServerData) {
            ((MixinServerData)(Object)copy).minecraftbc$isP2PServer = this.minecraftbc$isP2PServer;
            ((MixinServerData)(Object)copy).minecraftbc$p2pServerId = this.minecraftbc$p2pServerId;
            ((MixinServerData)(Object)copy).minecraftbc$originalHost = this.minecraftbc$originalHost;
            ((MixinServerData)(Object)copy).minecraftbc$originalPort = this.minecraftbc$originalPort;
        }
    }
}
