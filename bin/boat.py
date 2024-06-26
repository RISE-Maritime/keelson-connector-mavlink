import time
from pymavlink import mavutil
from enum import Enum


class Status(Enum):
    UNDEFINED = -1
    ARMED = 0
    DISARMED = 1
    EMERGENCY = 2


class ControlAuthority(Enum):
    UNDEFINED = -1
    MANUAL = 0
    REMOTE = 1
    AUTOMATIC = 2


class Boat:
    def __init__(self, connection_string, baud):
        """
        Initialize the boat model with a MAVLink connection.
        :param connection_string: Connection string for MAVLink
        """
        self.__connection_string = connection_string
        self.__baud = baud
        self.__vehicle = None
        self.__connected = False
        self.__heartbeat_received = False
        # self.__allow_rc_override = True ## temporarily disabled as we're using the controlauthority instead
        self.__confirm_commands = False
        self.__current_rudder_value = 1500  # center point for rc joysticks
        self.__current_throttle_value = 1500  # center point for rc joysticks
        self.__last_command_sent = None
        self.__mode_switch = None

        self.__connect()

        # we could make this more verbose
        self.__status: Status = Status.ARMED if self.is_armed() else Status.UNDEFINED

        self.__control_authority: ControlAuthority

        current_flight_mode = self.get_flight_mode()  # this didnt return the correct info from the heartbeat, it's not updated

        # we could use switch here, but then we lock ourselves to python 3.10+
        if current_flight_mode == 0:
            self.__control_authority = ControlAuthority.MANUAL

        elif current_flight_mode == 1:
            self.__control_authority = ControlAuthority.REMOTE

        elif current_flight_mode == 2:
            self.__control_authority = ControlAuthority.AUTOMATIC

        else:
            self.__control_authority = ControlAuthority.UNDEFINED

        self.__control_authority = ControlAuthority.REMOTE

    def get_vehicle(self):
        return self.__vehicle

    def __should_allow_rc_override(self):
        """
        Returns true if we should allow override, i.e. any mode above 0 in our currently defined modes
        """

        if self.__control_authority == ControlAuthority.UNDEFINED:
            self.__poll_rc_mode_switch()

        print(self.__control_authority.value)

        return self.__control_authority.value != 0

    def __keep_alive_rc_override(self):
        self.__update_steering()

    def check_rc_mode(self):
        self.__poll_rc_mode_switch()

        if self.__should_allow_rc_override():
            print("Should allow rc override")
            self.__keep_alive_rc_override()

    def __poll_rc_mode_switch(self):
        """
        Poll the state of RC channel 11
        """
        message = self.__vehicle.recv_match(type='RC_CHANNELS', blocking=True, timeout=1)
        if message:
            self.rc_channel_11_value = message.chan11_raw if hasattr(message, 'chan11_raw') else None
            if self.rc_channel_11_value is not None:
                print(f"RC Channel 11 value: {self.rc_channel_11_value}")
                if self.rc_channel_11_value > 1500 and self.__control_authority != ControlAuthority.REMOTE:
                    self.__control_authority = ControlAuthority.REMOTE
                    print("CONTROL AUTHORITY UPDATED TO REMOTE")
                elif self.rc_channel_11_value < 1500 and self.__control_authority != ControlAuthority.MANUAL:
                    self.__control_authority = ControlAuthority.MANUAL
                    print("CONTROL AUTHORITY UPDATED TO MANUAL")
            else:
                print("RC Channel 11 value not available in the message.")

    @property
    def heart_beat_received(self):
        return self.__heartbeat_received

    # @property
    # def allow_rc_override(self):
    #     """
    #     Get the current state of whether RC override is allowed.
    #     """
    #     return self.__allow_rc_override
    #
    # @allow_rc_override.setter
    # def allow_rc_override(self, should_allow):
    #     """
    #     Set whether to allow RC override.
    #     """
    #     self.__allow_rc_override = should_allow

    def __connect(self):
        """
        Establish a MAVLink connection to the vehicle.
        """
        print("Connecting to vehicle on:", self.__connection_string)
        self.__vehicle = mavutil.mavlink_connection(self.__connection_string)

    def wait_for_heartbeat(self):
        """
        Wait for the first heartbeat from the vehicle to confirm connection.
        """
        print("Waiting for vehicle heartbeat")
        if self.__vehicle.wait_heartbeat():
            self.__heartbeat_received = True
            self.__connected = True  # probably redundant
            print("Heartbeat received")

    def arm_vehicle(self):
        """
        Arm the vehicle
        :return: true if action succeeded, false otherwise
        """
        print("Arming vehicle")

        self.__vehicle.mav.command_long_send(
            self.__vehicle.target_system, self.__vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
            1,
            0, 0, 0, 0, 0, 0
        )

        if self.is_armed():
            self.__status = Status.ARMED
            print("VEHICLE ARMED")

            return True

        return False

    def disarm_vehicle(self):
        """
        Disarm the vehicle
        :return: true if action succeeded, false otherwise
        """
        print("DISARMING VEHICLE")

        self.__vehicle.mav.command_long_send(
            self.__vehicle.target_system, self.__vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
            0,
            0, 0, 0, 0, 0, 0
        )

        if not self.is_armed():
            self.__status = Status.DISARMED
            print("VEHICLE DISARMED")

            return True

        return False

    def is_armed(self):
        """
        Check if the vehicle is armed.
        :return: True if armed, False otherwise
        """
        heartbeat = self.__vehicle.recv_match(type='HEARTBEAT', blocking=True, timeout=1)

        if heartbeat:
            # Check if the vehicle is armed by examining the base_mode field
            armed = heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            return bool(armed)
        else:
            print("No heartbeat message received.")
            return False

    def set_speed(self, speed):
        """
        Set the target speed of the boat.
        :param speed: Speed in m/s
        """
        pass

    def change_heading(self, heading):
        """
        Change the boat's heading.
        :param heading: Heading in degrees
        """
        pass

    def close_connection(self):
        """
        Close the MAVLink connection.
        """
        if self.__vehicle:
            self.__vehicle.close()
            self.__connected = False
            print("Connection closed")

    def set_relay_on(self, relay_number):
        """
        Turns the specified relay on.
        :param vehicle: The vehicle connection
        :param relay_number: The relay number to turn on (default is 0 for Relay1)
        """
        # Send MAV_CMD_DO_SET_RELAY command to turn relay on
        self.__vehicle.mav.command_long_send(
            self.__vehicle.target_system, self.__vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_RELAY,
            0,
            relay_number, 1, 0, 0, 0, 0, 0
        )
        print(f"Relay{relay_number + 1} turned on")

    def set_relay_off(self, relay_number):
        """
        Turns the specified relay on.
        :param vehicle: The vehicle connection
        :param relay_number: The relay number to turn on (default is 0 for Relay1)
        """
        # Send MAV_CMD_DO_SET_RELAY command to turn relay on
        self.__vehicle.mav.command_long_send(
            self.__vehicle.target_system, self.__vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_RELAY,
            0,
            relay_number, 0, 0, 0, 0, 0, 0
        )
        print(f"Relay{relay_number + 1} turned off")

    def emergency_stop(self):
        """Emergency stop, calls the disable propulsion function. Named for clarity and to enable additional actions"""
        print("EMERGENCY STOP, DISABLING PROPULSION")
        self.disable_propulsion()

    def disable_propulsion(self):
        """
        Switches off the power to the motors through the beefy relay
        """
        print("DISABLING PROPULSION")
        self.set_relay_off(1)

    def enable_propulsion(self):
        """
        Switches on the power to the motors through the beefy relay
        """
        print("ENABLING PROPULSION")
        self.set_relay_on(1)

    def set_rudder(self, steering_value: int):
        """
        Set the steering of the boat by overriding the RC channel.
        :param steering_value: The PWM value to set for the steering channel (usually between 1000 and 2000)
        """
        if not self.__connected:
            print("Vehicle not connected")
            return

        try:
            received_value = int(steering_value)

            if received_value >= 1100 and received_value <= 1900:
                self.__current_rudder_value = int(steering_value)

        except:
            print(f"Invalid steering value: {steering_value}")
            return

        if self.__should_allow_rc_override():
            self.__update_steering()
            print(f"Steering set to {steering_value}")

        else:
            print("Overriding RC channels currently disabled ")

    def set_throttle(self, throttle_value):
        """
        Set the steering of the boat by overriding the RC channel.
        :param steering_value: The PWM value to set for the steering channel (usually between 1000 and 2000)
        """
        if not self.__connected:
            print("Vehicle not connected")
            return

        try:
            received_value = int(throttle_value)

            if received_value >= 1100 and received_value <= 1900:
                self.__current_throttle_value = int(throttle_value)

        except:
            print(f"Invalid steering value: {throttle_value}")
            return

        if self.__should_allow_rc_override():
            self.__update_steering()
            print(f"Throttle set to {throttle_value}")

        else:
            print("Overriding RC channels currently disabled ")

    def set_throttle_differential(self, throttle_left, throttle_right):
        """
        Set the steering of the boat by overriding the RC channel.
        :param steering_value: The PWM value to set for the steering channel (usually between 1000 and 2000)
        """

        raise NotImplementedError()

        if not self.__connected:
            print("Vehicle not connected")
            return

        else:
            print("Overriding RC channels currently disabled ")

    def __update_steering(self):
        """
        Controls both rudder and throttle values
        """

        print(f"Updated steering steering: {self.__current_rudder_value}, throttle: {self.__current_throttle_value}")
        self.__vehicle.mav.rc_channels_override_send(
            self.__vehicle.target_system,  # target_system
            self.__vehicle.target_component,  # target_component
            self.__current_rudder_value,
            self.__current_throttle_value,  # might be unnecessary
            self.__current_throttle_value,
            0, 0, 0, 0, 0
            # Other RC channels not overridden
        )

    def set_raw_servo(self, servo_number, pwm_value):
        """
        Set a raw servo output.

        :param servo_number: The servo output number (e.g., 1 for SERVO1_OUTPUT).
        :param pwm_value: The PWM value to set (usually between 1000 and 2000).
        """
        if not self.__connected:
            print("Vehicle not connected")
            return

        # Ensure PWM value is within a safe range
        pwm_value = max(1000, min(pwm_value, 2000))

        # MAV_CMD_DO_SET_SERVO command
        self.__vehicle.mav.command_long_send(
            self.__vehicle.target_system,
            self.__vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0,  # 0 for confirmation
            servo_number,  # Servo number
            pwm_value,  # PWM value
            0, 0, 0, 0, 0  # Unused parameters
        )

        print(f"Set servo {servo_number} to PWM {pwm_value}")

    def get_flight_mode(self):
        """
        Retrieve the current flight mode from the vehicle.

        :return: The name of the current flight mode as a string.
        """
        # Fetch the latest heartbeat message
        heartbeat = self.__vehicle.recv_match(type='HEARTBEAT', blocking=True, timeout=1)

        if heartbeat:
            mode_id = heartbeat.custom_mode
            # apm_mode_mapping = {
            #     0: 'MANUAL',
            #     1: 'ACRO',
            #     2: 'STEERING',
            #     3: 'HOLD',
            #     4: 'LOITER',
            #     5: 'FOLLOW',
            #     6: 'SIMPLE',
            # }
            # mode_name = apm_mode_mapping.get(mode_id, "UNKNOWN")

            return mode_id

        else:
            print("No heartbeat message received.")
            return None


# example usage below

if __name__ == "__main__":
    connection_string = '/dev/cu.usbmodem2101'
    boat = Boat(connection_string=connection_string, baud=115200)
    # boat.connect()
    boat.wait_for_heartbeat()

    # boat.enable_propulsion()
    # time.sleep(1)

    # # time.sleep(1)
    # boat.set_steering(1600)
    # time.sleep(1)
    # boat.set_steering(1500)

    # time.sleep(1)
    # boat.set_throttle(1800)

    # time.sleep(2)

    while True:

        msg = boat.get_vehicle().recv_msg()

        if msg:
            print(msg)

        # attitude_msg = boat.vehicle.recv_match(type='ATTITUDE', blocking=True, timeout=0.1)
        # gps_msg = boat.vehicle.recv_match(type='GPS_RAW_INT', blocking=True, timeout=0.1)
        # battery_msg = boat.vehicle.recv_match(type='BATTERY_STATUS', blocking=True, timeout=0.1)
        # vfr_hud_msg = boat.vehicle.recv_match(type='VFR_HUD', blocking=True, timeout=0.1)
        # radio_status_msg = boat.vehicle.recv_match(type='RADIO_STATUS', blocking=True, timeout=0.1)
        # date = datetime.datetime.now()
        # timestamp = date.strftime('%H:%M:%S')
        # if vfr_hud_msg:
        #     print(f"[{timestamp}] Heading: {vfr_hud_msg.heading} degrees")
        # if attitude_msg:
        #     print(f"[{timestamp}] Pitch: {attitude_msg.pitch}, Roll: {attitude_msg.roll}, Yaw: {attitude_msg.yaw}")
        # if gps_msg:
        #     print(
        #         f"[{timestamp}] GPS Lat: {gps_msg.lat / 1e7}, Lon: {gps_msg.lon / 1e7}, Alt: {gps_msg.alt / 1e3} meters")
        # if battery_msg:
        #     battery_voltage = battery_msg.voltages[0] / 1000.0  # Convert millivolts to volts
        #     print(f"[{timestamp}] Battery Voltage: {battery_voltage}V")
        # if radio_status_msg:
        #     print(
        #         f"[{timestamp}] Radio: RSSI {radio_status_msg.rssi}/255, Remote RSSI {radio_status_msg.remrssi}/255, Noise {radio_status_msg.noise}/255, Remote Noise {radio_status_msg.remnoise}/255, TX Buffer {radio_status_msg.txbuf}%")
        time.sleep(0.1)
    boat.close_connection()
