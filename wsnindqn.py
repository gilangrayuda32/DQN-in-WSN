
## This code was created by Gilang Raka Rayuda Dewa ##
## 16 December 2022 ##
## The purpose is to select the best routing strategy of WSN by utilizing Deep Q-Neural Network ##

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import math
import random

# Parameter used
ALPHA = 0.0001
NNodes = 10
CNodes = (100, 256, 256)
BatchSize= 32
EnergyTresh = 30
Radius = 500
AveragePower = 0.1


class env():
    def __init__(self, resource, NNodes, CNodes):
        self.resource = resource
        self.NNodes = NNodes
        self.dist = DistNodes(Radius, NNodes)
        self.MessageTransmitted = 0
        self.Steps = 0

        # State During
        self.data = CNodes[0]
        self.delay = CNodes[1]
        self.BatteryCapacity = CNodes[2]
        self.DataNode = [0] * NNodes
        self.BatteryNode = [CNodes[1]] * NNodes

        # To confirm if the process has finished
        self.done = False

    # To consider data received
    def DataReceived(self, node):

        # Confirm that there is no data transmitted
        if self.DataNode[node] == 0:
            return None

        # generate random data of 0s and 1s
        data = np.ones(shape=(self.data, 1))
        data[1:50] = 0
        np.random.shuffle(data)
        return data.flatten()
    
        # To consider transmission process
    def transmit(self, Actions):
        datatransmit = []
        actiontransmit = Actions.view(-1).numpy()

        # Obtain transmission data
        for i in range(self.NNodes):
            if actiontransmit[i]:
                if (self.BatteryNode[i] > 1):
                    datatransmit.append(self.DataReceived(i))
                    self.MessageTransmitted += 1
                    self.BatteryNode[i] -= 1
                    self.TxNode[i] += 1
                else:
                    datatransmit.append(None)
            else:
                datatransmit.append(None)

        Signal = self.resource.MIMOTransmit(datatransmit)
        obs = np.dot(self.dist, Signal)

        return obs

    # Calculate Energy Consumption
    def SensorUsage(self):
        return self.MessageTransmitted / self.Steps

    # Calculate Actual Energy
    def ActualEnergyConsump(self):
        self.AverageBattery = sum(self.BatteryNode)/len(self.BatteryNode)
        self.RemEnergy= (self.MessageTransmitted / self.Steps)*self.AverageBattery
        return self.RemEnergy

    # Calculate Baterry Capacity
    def BatteryInitCapacity(self, AveragePower=0.1):
        for i in range(self.NNodes):
            self.BatteryNode[i] += AveragePower + (AveragePower / 20) * np.random.normal()
        return self.BatteryNode

    def GetState(self):
        # Get State of Transmission
        MinTx = min(self.TxNode)
        MaxTx = max(self.TxNode) + 1
        normTx = [(x) / (MaxTx) for x in self.TxNode]

        # Get State of Battery and Latency
        normBattery = [x / self.BatteryCapacity for x in self.BatteryNode]
        normLatency = [x / self.delay for x in self.DataNode]
        return [normLatency, normBattery, normTx]


    def GetReward(self, Actions):
        actiontransmit = Actions.view(-1).numpy()
        # If sensor node action is 0, reward minus
        for i in range(self.NNodes):
            if (self.BatteryNode[i] < EnergyTresh):
                if (actiontransmit[i] == 0):
                    reward = 0
                else:
                    reward = self.TxNode[i] / (self.MessageTransmitted + 1)
            else:
                # If sensor node do transmit, there will be rwo reward
                if (actiontransmit[i] == 1):
                    reward = 0
                else:
                    reward = self.TxNode[i] / (self.MessageTransmitted + 1)
        return reward

    # Get State of Each Node
    def GetStateNode(self, IDSensor):
        _, reward, _ = self.Step(torch.zeros(self.NNodes + 1))
        return self.DataNode[IDSensor], self.BatteryNode[IDSensor], reward

        # To store history of Message Transmitted

    # Action and Reward
    def Step(self, Actions):
        reward = self.GetReward(Actions)
        obs = self.transmit(Actions)
        self.Steps += 1
        return obs, reward, self.GetState()

    def ConcentenateData(self, vals):
        for i in range(len(vals)):
            self.DataNode[i] += vals[i]

    # To reset all parameter in initial value
    def reset(self):
        self.MessageTransmitted = 0
        self.Steps = 0
        self.DataNode = [np.random.randint(100, high=200) for _ in range(NNodes)]
        self.BatteryNode = [self.BatteryCapacity] * self.NNodes
        self.done = False
        self.TxNode = [0] * self.NNodes
        return self.GetState()

    def GetHistory(self):
        return [x / self.MessageTransmitted for x in self.TxNode if x is not None]

class resource():

    def MIMOTransmit(self, messages):
        assert (len(messages) > 0), "No Messages to send"
        # Check if there is a message to send; if not, send back 0s
        if all(x is None for x in messages):
            return np.zeros(shape=(len(messages), CNodes[0]))

        # fill in the first block
        if messages[0] is not None:
            W = messages[0].reshape((1, CNodes[0]))
        else:
            W = np.zeros(shape=(1, CNodes[0]))
        #
        if (len(messages) > 1):
            for msg in messages[1:]:
                if msg is not None:
                    # print(msg.shape)
                    wave = msg.reshape((1, CNodes[0]))
                    W = np.concatenate((W, wave), axis=0)
                else:
                    W = np.concatenate((W, np.zeros(shape=(1, CNodes[0]))))
        return W


class Agent():

    def Init(self, net):
        self.agent = net

    def Call(self, x):
        if (isinstance(x, np.ndarray)):
            return self.agent(torch.tensor(x))
        else:
            return self.agent(x)

    def Parameters(self):
        return self.agent.parameters()


# DQN Class
# To establish neural network
class QNeuralNetwork(nn.Module):
    def __init__(self, NNodes):
        super().__init__()
        self.NNodes = NNodes
        self.LayerInput = nn.Linear(3 * NNodes, 28)
        self.HiddenLayer1 = nn.Linear(28, 18)
        self.HiddenLayer2 = nn.Linear(18, 18)
        self.LayerOutput = nn.Linear(18, NNodes)

    def forward(self, x):
        x = F.relu(self.LayerInput(x))
        x = F.relu(self.HiddenLayer1(x))
        x = F.relu(self.HiddenLayer2(x))
        x = self.LayerOutput(x)
        return x


# DQN Agent
class DQNAgent():
    def __init__(self, net, NNodes, ActionOptions=NNodes + 1, epsilon=0,
                 epsilon_decay=1.0):  # ActionOptions = Relay + One Direct to the BS
        self.NNodes = NNodes
        self.agent = net
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.ActionOptions = ActionOptions

    def chooseAction(self, obs):
        QValue = self.agent(obs)  # N x 1 x NNodes+1
        BatchSize = tuple(obs.size())
        Actions = torch.zeros(size=(BatchSize[0], self.NNodes, 1))
        QMax, QArgMax = torch.max(QValue.view(BatchSize[0], self.NNodes), 1)

        for i in range(BatchSize[0]):
            if (np.random.rand() < self.epsilon):
                Actions[i, np.random.randint(0, high=self.NNodes), 0] = 1
            else:
                Actions[i, QArgMax[i], 0] = 1
        return Actions, QMax

    def Parameters(self):
        return self.agent.parameters()

    def set_epsilon(self, epsilon):
        self.epsilon = epsilon

    def update_epsilon(self):
        self.epsilon *= self.epsilon_decay


# To do replay
class ExperienceBuffer:
    def __init__(self, Capacity, ValGamma=1, rollout=2):
        self.Actions = [None] * Capacity
        self.Rewards = [None] * Capacity
        self.States = [None] * Capacity
        self.PrevStates = [None] * Capacity
        self.Observ = [None] * Capacity
        self.Capacity = Capacity

        self.QValue = [0] * Capacity
        self.QTarget = [None] * Capacity
        self.QActual = [None] * Capacity
        self.Step = 0
        self.LengthRoullout = rollout
        self.ValGamma = ValGamma
        self.filled = 0

    def add(self, Observ, reward, action, state=None, PrevState=None, QActual=None, QTarget=0):
        q = reward

        Routing = (self.Step) % self.Capacity

        for i in range(0, self.LengthRoullout):
            BackwardRouting = (self.Step - i) % self.Capacity
            if (self.QValue[BackwardRouting] is not None):
                self.QValue[BackwardRouting] += q
                q *= self.ValGamma

        self.Rewards[Routing] = reward
        self.States[Routing] = state
        self.PrevStates[Routing] = PrevState
        self.Step += 1

        self.QTarget[Routing] = QTarget
        self.QActual[Routing] = QActual
        self.Observ[Routing] = Observ

        return self.Step

    def sample(self, num=1):
        Items = min(self.Capacity, self.Step)
        SampleIndex = random.sample(range(0, Items), num)

        ObservSample = []
        ActionSample = []
        Statesample = []
        PrevStateSample = []
        r_sample = []

        QValSample = []
        QTargetSample = []
        QActualSample = []

        for idx in SampleIndex:
            ObservSample.append(self.Observ[idx])
            r_sample.append(self.Rewards[idx])
            ActionSample.append(self.Actions[idx])
            QValSample.append(self.QValue[idx])
            Statesample.append(self.States[idx])
            PrevStateSample.append(self.PrevStates[idx])
            QTargetSample.append(self.QTarget[idx])
            QActualSample.append(self.QActual[idx])

        return ObservSample, r_sample, ActionSample, QValSample, Statesample, PrevStateSample, QActualSample, QTargetSample

    def isReady(self, required_num):
        return (self.Step > required_num)

## Define severat important parameter
#  Define distance among nodes as important parameter for WSN routing
def DistNodes(radCell, NNodes):
    Dist = np.zeros(shape=(NNodes, NNodes), dtype=np.float32)
    for i in range(NNodes):
        for j in range(NNodes):
            if (i == j):
                Dist[i, j] = 1
            else:
                DistX = np.cos(2 * np.pi * i / NNodes) - np.cos(2 * np.pi * j / NNodes)
                DistY = np.sin(2 * np.pi * i / NNodes) - np.sin(2 * np.pi * j / NNodes)
                Dist[i, j] = ((radCell ** 2) * (DistX ** 2 + DistY ** 2))

    return Dist

def ListtoTensor(list_of_tensors):
    #shapes = list_of_tensors[0].shape
    res = [i for i in list_of_tensors if i is not None]
    shape = res[0].numpy().shape
    if(len(shape)<2):
        shape = (shape[0], 1)
    output = res[0].view(1,1,-1)
    for t in res[1:]:
        if(t is not None):
            item = t.view(1,1,-1)
            output = torch.cat((output,item), dim = 0)
    return output

def ScalarsToTensor(list_of_scalars):
    res = [i for i in list_of_scalars if i is not None]
    return torch.Tensor(res)

####################################
### Main Simulation ###
dqn = QNeuralNetwork(NNodes)
DQ_agent = DQNAgent(dqn, NNodes, epsilon=1.0, epsilon_decay=0.9)
optimizer = optim.Adam(DQ_agent.Parameters(), lr=ALPHA)
buffer = ExperienceBuffer(10000)
episodenum = 50

EnvironmentWSN = env(resource(), NNodes, CNodes)
LossParameter = []
RewardParameter = []
EnergyConsumpParameter = []
RewardParameter = []
AvgEpisodeRewardParameter = []
HistoryParameter = []
DQNNet = np.zeros(episodenum)
DQLatNet = np.zeros(episodenum)
for episode in range(episodenum): 
    episode_Rewards = []

    obs = EnvironmentWSN.reset()
    DQ_agent.update_epsilon()

    for i in range(4096):
        # Agent Interacts with environment
        input_obs = (torch.tensor(obs, dtype=torch.float32).view(1, -1) / 512)

        action, Q = DQ_agent.chooseAction(input_obs)
        _, reward, obs = EnvironmentWSN.Step(action)
        buffer.add(input_obs, reward, action)
        RewardParameter.append(np.mean(RewardParameter))
        episode_Rewards.append(reward)
        RewardParameter.append(reward)
        EnvironmentWSN.ConcentenateData(np.random.randint(0, high=2, size=(NNodes,)))
        EnergyConsumpParameter.append(EnvironmentWSN.SensorUsage())
        EnergyConsumpParameter.append(EnvironmentWSN.BatteryInitCapacity())

        if (buffer.isReady(1000) and (i % 2 == 0)):
            obs_batch, reward_batch, action_batch, q_batch, _, _,_,_ = buffer.sample(BatchSize)
            input_obs_batch = (torch.tensor(obs_batch[1], dtype=torch.float32).view(1, -1) / 512)
            _, Q_vals = DQ_agent.chooseAction(input_obs_batch)
            loss = F.mse_loss(ScalarsToTensor(q_batch).view(-1), Q_vals.view(-1))
            LossParameter.append(loss)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()      
    AvgEpisodeRewardParameter.append(np.mean(episode_Rewards))
    HistoryParameter.append(EnvironmentWSN.GetHistory())
    print(
        f'e {episode}: \t Percentage of Sensor Usage: {EnvironmentWSN.SensorUsage()} \t Actual Energy Consumption  {EnvironmentWSN.ActualEnergyConsump()} \t \n'
        f'\t Average Reward: {np.mean(episode_Rewards)}                 \t Average Loss: {loss} \t  \n')
    DQNNet[episode] = EnvironmentWSN.SensorUsage()
    DQLatNet[episode] = EnvironmentWSN.ActualEnergyConsump()


plt.figure(1)
fig, ax = plt.subplots()
ax.plot(DQNNet, linestyle='solid')
ax.legend(['DQN'])
ax.set_title('Percentage of Sensor Usage')
ax.set_xlabel('Time Step')
ax.set_ylabel('Percentage of Sensor Usage')

plt.figure(2)
fig, ax = plt.subplots()
ax.plot(DQLatNet, linestyle='solid')
ax.legend(['DQN'])
ax.set_title('Actual Energy Consumption ')
ax.set_xlabel('Time Step')
ax.set_ylabel('Energy Consumption (Joule)')
plt.show()
