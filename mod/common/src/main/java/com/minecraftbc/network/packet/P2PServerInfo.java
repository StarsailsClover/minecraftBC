package com.minecraftbc.network.packet;

/**
 * P2P 服务器信息
 */
public class P2PServerInfo {
    public String id;              // 服务器唯一ID
    public String name;            // 显示名称
    public String description;     // 描述/MOTD
    public String host;          // P2P节点主机
    public int port;             // P2P节点端口
    public int latency;          // 延迟(ms)
    public int playerCount;      // 在线玩家数
    public int maxPlayers;       // 最大玩家数
    public String version;       // 游戏版本
    public String icon;          // Base64服务器图标（可选）
    
    @Override
    public String toString() {
        return String.format("P2PServer{id=%s, name=%s, host=%s:%d, latency=%dms}",
            id, name, host, port, latency);
    }
}
