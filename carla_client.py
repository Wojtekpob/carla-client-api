import carla
import yaml
import os
import time


class CarlaClient:
    def __init__(self, config):
        """
        Initializes the CARLA client based on configuration.

        :param config: Configuration dictionary.
        """
        self.config = config

        self.host = self.config['carla']['host']
        self.port = self.config['carla']['port']
        self.timeout = self.config['carla']['timeout']
        self.image_save_path = self.config['camera']['image_save_path']
        self.sampling_time = self.config['camera']['sampling_time']

        self.autopilot = self.config['vehicle'].get('autopilot', False)

        self.client = carla.Client(self.host, self.port)
        self.client.set_timeout(self.timeout)

        self.map_name = self.config['carla'].get('map', 'Town01')
        self._load_map(self.map_name)

        self.world = self.client.get_world()

        self.vehicle = None
        self.camera = None

        self.camera_callback = None

        self._last_image_time = None

        self._initialize_simulation()

    def _load_map(self, map_name):
        """
        Loads the specified map in the CARLA simulator.

        :param map_name: Name of the map to load (e.g., 'Town01', 'Town02', etc.).
        """
        available_maps = self.client.get_available_maps()
        if f"/Game/Carla/Maps/{map_name}" in available_maps:
            print(f"Loading map: {map_name}")
            self.client.load_world(map_name)
        else:
            raise ValueError(f"Map {map_name} is not available. Available maps: {available_maps}")

    def _initialize_simulation(self):
        """
        Initializes the vehicle and camera in the simulation.
        """
        blueprint_library = self.world.get_blueprint_library()

        vehicle_bp = blueprint_library.find(self.config['vehicle']['blueprint'])
        spawn_point = self.world.get_map().get_spawn_points()[0]

        self.vehicle = self.world.spawn_actor(vehicle_bp, spawn_point)
        print(f'Spawned vehicle: {self.vehicle.type_id}')

        self.vehicle.set_autopilot(self.autopilot)
        if self.autopilot:
            print('Autopilot is enabled for the vehicle.')

        camera_bp = blueprint_library.find('sensor.camera.rgb')
        camera_bp.set_attribute('image_size_x', str(self.config['camera']['image_size_x']))
        camera_bp.set_attribute('image_size_y', str(self.config['camera']['image_size_y']))
        camera_bp.set_attribute('fov', str(self.config['camera']['fov']))

        camera_transform = carla.Transform(
            carla.Location(
                x=self.config['camera']['transform']['x'],
                y=self.config['camera']['transform']['y'],
                z=self.config['camera']['transform']['z']
            ),
            carla.Rotation(
                pitch=self.config['camera']['transform']['pitch'],
                yaw=self.config['camera']['transform']['yaw'],
                roll=self.config['camera']['transform']['roll']
            )
        )

        self.camera = self.world.spawn_actor(camera_bp, camera_transform, attach_to=self.vehicle)
        print('Spawned camera')

        if not os.path.exists(self.image_save_path):
            os.makedirs(self.image_save_path)

    def set_camera_callback(self, callback):
        """
        Sets the camera callback function.

        :param callback: Function invoked after every image from the camera.
        """
        self.camera_callback = callback
        self.camera.listen(self._camera_listener)

    def _camera_listener(self, image):
        """
        Function invoked after every image from the camera.

        :param image: Image from the camera.
        """
        current_time = time.time()
        if self._last_image_time is not None:
            if current_time - self._last_image_time < self.sampling_time:
                return
        self._last_image_time = current_time

        image_filename = os.path.join(self.image_save_path, f'{image.frame:06d}.png')
        image.save_to_disk(image_filename)

        if self.camera_callback is not None:
            self.camera_callback(image)

    def stop(self):
        """
        Frees up resources.
        """
        if self.camera is not None:
            self.camera.stop()
            self.camera.destroy()
            self.camera = None
            print('Camera destroyed')
        if self.vehicle is not None:
            self.vehicle.destroy()
            self.vehicle = None
            print('Vehicle destroyed')

    def __del__(self):
        """
        Destructor - ensures resources are freed.
        """
        self.stop()