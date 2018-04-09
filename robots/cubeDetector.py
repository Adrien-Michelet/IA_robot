import os
import numpy as np
import cv2
import math
import time

class CubeDetector:

    def __init__(self):
        self.isRaspberry = "arm" in os.popen("uname -m").read()
        if self.isRaspberry:
            from picamera.array import PiRGBArray
            from picamera import PiCamera
        self.camera = None
        self.cameraBuffer = None
        self.cameraImage = None

        self.cubeColorsHSV = {"yellow": [44, 100, 97, 10],  # H,S,V,Range
                             "green": [96, 61, 60, 20],
                             "blue": [198, 100, 69, 20],
                             "black": [240, 13, 6, 10],
                             "orange": [19, 81, 82, 5]}
        self.initCamera()

    def getCubeList(self):
        for i in range(0,10):
            self.readCameraImage()
        #self.cameraImage = cv2.imread("../../imageArea.jpg".format(random.randint(1, 4)))
        self.cameraImage = cv2.resize(self.cameraImage, (255, 255))
        #self.previewArmCoordinates(self.cameraImage)
        imgCubeColor, maskCubeColor = self.filterColors(self.cameraImage)
        cubes = self.findCubes(imgCubeColor, maskCubeColor, self.cameraImage)
        for c in cubes:
            c["position"] = self.transformPointInArmReferential(c["position"])
        #cv2.imshow('final', cameraImage)
        return cubes

    def initCamera(self):
        if (self.isRaspberry):
            self.camera = PiCamera()
            self.camera.resolution = (640, 480)
            self.cameraBuffer = PiRGBArray(self.camera, size=(640, 480))
            time.sleep(0.1)
        else:
            self.camera = cv2.VideoCapture(0)

    def readCameraImage(self):
        if self.isRaspberry:
            self.cameraBuffer.truncate(0)  # reset buffer
            self.camera.capture(self.cameraBuffer, format="bgr", resize=(640, 480))
            self.cameraImage = self.cameraBuffer.array
        else:
            retVal, self.cameraImage = self.camera.read()

    def filterColors(self, img):
        height, width, channels = img.shape
        imgBlur = cv2.medianBlur(img, 5)
        imgBlur = cv2.blur(imgBlur, (7, 7))
        hsv = cv2.cvtColor(imgBlur, cv2.COLOR_BGR2HSV)
        finalMask = np.zeros((height, width), np.uint8)
        kernel = np.ones((5, 5), np.uint8)
        for key in self.cubeColorsHSV:
            color = self.cubeColorsHSV[key]
            lower = np.array([max(0, color[0] / 2 - color[3]), 140, 50])
            upper = np.array([min(255, color[0] / 2 + color[3]), 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.erode(mask, kernel, iterations=2)
            finalMask = cv2.add(finalMask, mask)
        img = cv2.bitwise_and(img, img, mask=finalMask)
        return img, finalMask

    def transformPointInArmReferential(self, point):
        xRatio = 255.0 / 640.0  # srcPoint are in a VGA referential
        yRatio = 255.0 / 480.0  # srcPoint are in a VGA referential
        srcPoints = np.float32([[132 * xRatio, 327 * yRatio]
                                   , [410 * xRatio, 260 * yRatio]
                                   , [391 * xRatio, 420 * yRatio]
                                   , [207 * xRatio, 464 * yRatio]])
        dstPoints = np.float32([[0, 0], [100, 0], [100, 100], [0, 100]])
        M = cv2.getPerspectiveTransform(srcPoints, dstPoints)
        pt = np.array([[point[0], point[1]]], dtype="float32")
        pt = np.array([pt])
        result = cv2.perspectiveTransform(pt, M)
        return [result[0][0][0], 100 - result[0][0][1]]

    def previewArmCoordinates(self, img):
        xRatio = 255.0 / 640.0  # srcPoint are in a VGA referential
        yRatio = 255.0 / 480.0  # srcPoint are in a VGA referential
        srcPoints = np.float32(
            [[132 * xRatio, 327 * yRatio], [410 * xRatio, 260 * yRatio], [391 * xRatio, 420 * yRatio],
             [207 * xRatio, 464 * yRatio]])
        imgPrev = img.copy()
        cv2.line(imgPrev, (srcPoints[0][0], srcPoints[0][1]), (srcPoints[1][0], srcPoints[1][1]), (0, 255, 0), 2)
        cv2.line(imgPrev, (srcPoints[1][0], srcPoints[1][1]), (srcPoints[2][0], srcPoints[2][1]), (0, 255, 0), 2)
        cv2.line(imgPrev, (srcPoints[2][0], srcPoints[2][1]), (srcPoints[3][0], srcPoints[3][1]), (0, 255, 0), 2)
        cv2.line(imgPrev, (srcPoints[3][0], srcPoints[3][1]), (srcPoints[0][0], srcPoints[0][1]), (0, 255, 0), 2)
        cv2.imshow("preview", imgPrev)

    def findCubes(self, img, mask, rawImage):
        cubeList = []
        draw = False
        contours = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = contours[1]
        for c in cnts:
            rect = cv2.minAreaRect(c)
            area = rect[1][0] * rect[1][1]
            orientation = rect[2]
            # Reject small or large contours
            if area < 500 or area > 5000:
                continue

            # Find cube center
            box = cv2.boxPoints(rect)
            box = np.int0(box)
            minY = 9999
            meanXLow = 0
            meanXHigh = 0
            for point in box:
                if point[1] < rect[0][1]:  # High point
                    meanXHigh += point[0]
                else:
                    meanXLow += point[0]
                if minY > point[1]:
                    minY = point[1]
            meanXLow /= 2
            meanXHigh /= 2
            cubeX = np.int0(rect[0][0])
            cubeY = np.int0(minY + max(rect[1][0], rect[1][1]) / 2)
            if rect[1][0] * 1.3 < rect[1][1] or rect[1][1] * 1.3 < rect[1][0]:
                cubeY = np.int0(minY + max(rect[1][0], rect[1][1]) / 2.7)
                cubeX = np.int0(meanXHigh * 0.6 + meanXLow * 0.4)
            grabPoint = (cubeX, cubeY)

            # find rotation
            rotation = 90 - orientation

            # find color
            cubeColor = ""
            colorScore = 0
            for key in self.cubeColorsHSV:
                color = self.cubeColorsHSV[key]
                lower = np.array([max(0, color[0] / 2 - color[3]), 140, 50])
                upper = np.array([min(255, color[0] / 2 + color[3]), 255, 255])
                lookupSize = 30
                height, width, channels = rawImage.shape
                subImage = rawImage[max(0, grabPoint[1] - lookupSize / 2)
                :min(height, grabPoint[1] + lookupSize / 2)
                , max(0, grabPoint[0] - lookupSize / 2)
                           :min(width, grabPoint[0] + lookupSize / 2)]
                subImage = cv2.medianBlur(subImage, 9)
                subImage = cv2.blur(subImage, (3, 3))
                hsv = cv2.cvtColor(subImage, cv2.COLOR_BGR2HSV)
                found = cv2.inRange(hsv, lower, upper)
                score = np.sum(found)
                if score > colorScore:
                    cubeColor = key
                    colorScore = score

            cubeList.append({'position': grabPoint, 'rotation': rotation, 'color': cubeColor})

            # show the image
            if draw:
                orientationPoint = (
                    np.int0(grabPoint[0] + 20 * math.cos((orientation - 90) * 3.1415 / 180.0))
                    , np.int0(grabPoint[1] + 20 * math.sin((orientation - 90) * 3.1415 / 180.0))
                )
                cv2.drawContours(img, [box], -1, (0, 255, 0), 2)
                cv2.circle(img, grabPoint, 5, (0, 255, 0), 2)
                cv2.line(img, grabPoint, orientationPoint, (0, 255, 0), 2)
                cv2.putText(img, "{0} {1}".format(np.int0(rotation), cubeColor), (cubeX - 20, cubeY - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                cv2.imshow("cubes", img)
        return cubeList