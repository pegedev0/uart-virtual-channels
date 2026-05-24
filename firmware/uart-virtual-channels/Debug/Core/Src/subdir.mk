################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../Core/Src/main.c \
../Core/Src/stm32f7xx_hal_msp.c \
../Core/Src/stm32f7xx_it.c \
../Core/Src/syscalls.c \
../Core/Src/sysmem.c \
../Core/Src/system_stm32f7xx.c \
../Core/Src/uartvc_crc.c \
../Core/Src/uartvc_frame.c \
../Core/Src/uartvc_hw.c \
../Core/Src/uartvc_link.c \
../Core/Src/uartvc_parser.c \
../Core/Src/uartvc_scheduler.c 

OBJS += \
./Core/Src/main.o \
./Core/Src/stm32f7xx_hal_msp.o \
./Core/Src/stm32f7xx_it.o \
./Core/Src/syscalls.o \
./Core/Src/sysmem.o \
./Core/Src/system_stm32f7xx.o \
./Core/Src/uartvc_crc.o \
./Core/Src/uartvc_frame.o \
./Core/Src/uartvc_hw.o \
./Core/Src/uartvc_link.o \
./Core/Src/uartvc_parser.o \
./Core/Src/uartvc_scheduler.o 

C_DEPS += \
./Core/Src/main.d \
./Core/Src/stm32f7xx_hal_msp.d \
./Core/Src/stm32f7xx_it.d \
./Core/Src/syscalls.d \
./Core/Src/sysmem.d \
./Core/Src/system_stm32f7xx.d \
./Core/Src/uartvc_crc.d \
./Core/Src/uartvc_frame.d \
./Core/Src/uartvc_hw.d \
./Core/Src/uartvc_link.d \
./Core/Src/uartvc_parser.d \
./Core/Src/uartvc_scheduler.d 


# Each subdirectory must supply rules for building sources it contributes
Core/Src/%.o Core/Src/%.su Core/Src/%.cyclo: ../Core/Src/%.c Core/Src/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m7 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32F746xx -c -I../Core/Inc -I../Drivers/STM32F7xx_HAL_Driver/Inc -I../Drivers/STM32F7xx_HAL_Driver/Inc/Legacy -I../Drivers/CMSIS/Device/ST/STM32F7xx/Include -I../Drivers/CMSIS/Include -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfpu=fpv5-sp-d16 -mfloat-abi=hard -mthumb -o "$@"

clean: clean-Core-2f-Src

clean-Core-2f-Src:
	-$(RM) ./Core/Src/main.cyclo ./Core/Src/main.d ./Core/Src/main.o ./Core/Src/main.su ./Core/Src/stm32f7xx_hal_msp.cyclo ./Core/Src/stm32f7xx_hal_msp.d ./Core/Src/stm32f7xx_hal_msp.o ./Core/Src/stm32f7xx_hal_msp.su ./Core/Src/stm32f7xx_it.cyclo ./Core/Src/stm32f7xx_it.d ./Core/Src/stm32f7xx_it.o ./Core/Src/stm32f7xx_it.su ./Core/Src/syscalls.cyclo ./Core/Src/syscalls.d ./Core/Src/syscalls.o ./Core/Src/syscalls.su ./Core/Src/sysmem.cyclo ./Core/Src/sysmem.d ./Core/Src/sysmem.o ./Core/Src/sysmem.su ./Core/Src/system_stm32f7xx.cyclo ./Core/Src/system_stm32f7xx.d ./Core/Src/system_stm32f7xx.o ./Core/Src/system_stm32f7xx.su ./Core/Src/uartvc_crc.cyclo ./Core/Src/uartvc_crc.d ./Core/Src/uartvc_crc.o ./Core/Src/uartvc_crc.su ./Core/Src/uartvc_frame.cyclo ./Core/Src/uartvc_frame.d ./Core/Src/uartvc_frame.o ./Core/Src/uartvc_frame.su ./Core/Src/uartvc_hw.cyclo ./Core/Src/uartvc_hw.d ./Core/Src/uartvc_hw.o ./Core/Src/uartvc_hw.su ./Core/Src/uartvc_link.cyclo ./Core/Src/uartvc_link.d ./Core/Src/uartvc_link.o ./Core/Src/uartvc_link.su ./Core/Src/uartvc_parser.cyclo ./Core/Src/uartvc_parser.d ./Core/Src/uartvc_parser.o ./Core/Src/uartvc_parser.su ./Core/Src/uartvc_scheduler.cyclo ./Core/Src/uartvc_scheduler.d ./Core/Src/uartvc_scheduler.o ./Core/Src/uartvc_scheduler.su

.PHONY: clean-Core-2f-Src

