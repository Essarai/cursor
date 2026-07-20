package com.smartagri.api.entity;

import javax.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 设备实体类
 */
@Data
@Entity
@Table(name = "device")
public class Device {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * 设备地址/编号
     */
    private String address;
    
    /**
     * 设备名称
     */
    private String name;
    
    /**
     * 设备类型（1-传感器，2-控制器，3-网关，4-摄像头，5-其他）
     */
    private Integer type;
    
    /**
     * 设备型号
     */
    private String model;
    
    /**
     * 所属地块ID
     */
    private Long landBlockId;
    
    /**
     * 父设备地址（网关）
     */
    private String parentAddress;
    
    /**
     * 设备状态（0-离线，1-在线，2-故障）
     */
    private Integer status;
    
    /**
     * 是否开启（0-关闭，1-开启）
     */
    private Integer isOn;
    
    /**
     * 安装位置
     */
    private String location;
    
    /**
     * 经度
     */
    private Double longitude;
    
    /**
     * 纬度
     */
    private Double latitude;
    
    /**
     * 厂商
     */
    private String manufacturer;
    
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    
    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
    
    /**
     * 是否删除（0-未删除，1-已删除）
     */
    private Integer isDeleted;
} 