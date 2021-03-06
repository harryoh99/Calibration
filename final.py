import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torch.utils.tensorboard import SummaryWriter
from sklearn.isotonic import IsotonicRegression as IS

os.chdir("/Users/jiooh/Documents/Jio/KAIST/2-2/개별연구/Data_Calibration")


class REData(Dataset):
    def __init__(self, x_data, y_data):
        indice = y_data.nonzero()[:, 0]
        self.data = x_data[indice]
        self.labels = y_data[indice]
        self.len = self.data.shape[0]

    def __getitem__(self, index):
        return self.data[index], self.labels[index]

    def __len__(self):
        return self.len



    



# 63560, 15, 667 for x
# 63560, 15, 1 for y
# For year 1


def criterion2(output, target):
    res = torch.abs(output - target) / target
    return res.mean()


def apply_dropout(m):
    if type(m)==nn.Dropout:
        m.train()

def getErr(x_list,):
    p=0.1
    err_list = []
    err = 0
    while(p<=1):
        count = 0
        phat = 0
        for i in range(len(x_list)):
            if(x_list[i]<=p):
                count +=1
        phat = count/len(x_list)
        err_list.append([p,phat])
        p+=0.1
    #weight is proportional to the phat, so just define weight as phat
    for i in range(len(err_list)):
        err += err_list[1]*(err_list[0]-err_list[1])*(err_list[0]-err_list[1])
    return err
        
def main(xpath, ypath):
    # Model

    model_dropout = nn.Sequential(
        nn.Linear(667, 300),
        nn.ReLU(),
        nn.Dropout(p=0.1),
        nn.Linear(300, 100),
        nn.ReLU(),
        nn.Dropout(p=0.1),
        nn.Linear(100, 20),
        nn.ReLU(),
        nn.Linear(20, 1),
    )

    # DATA LOAD/SPLIT
    x = torch.from_numpy(np.load(xpath))
    y = torch.from_numpy(np.load(ypath))

    x_data = x[:, 0, :].float()
    y_data = y[:, 0, :].float()
    for i in range(1, 15):
        temp_x = x[:, i, :].float()
        temp_y = y[:, i, :].float()
        x_data = torch.cat((x_data, temp_x), dim=0)
        y_data = torch.cat((y_data, temp_y), dim=0)

    dataset_size = x_data.shape[0]  # (63560*15,667)
    validation_split = 0.01

    indices = list(range(dataset_size))
    split = int(np.floor(validation_split * dataset_size))
    np.random.shuffle(indices)
    train_indices, val_indices = indices[split:], indices[:split]

    train_x = x_data[train_indices]
    train_y = y_data[train_indices]

    test_x = x_data[val_indices]
    test_y = y_data[val_indices]

    train_dataset = REData(train_x, train_y)
    test_dataset = REData(test_x, test_y)
    batch_size = 50

    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True
    )
    validation_loader = torch.utils.data.DataLoader(test_dataset, shuffle=True)

    learning_rate = 0.01
    optimizer_dropout = optim.Adam(model_dropout.parameters(), lr=learning_rate)
    num_epoch = 50



    training2_dropout_loss = []
    training2_dropout_epoch_loss = []

    model_dropout.train()
    
    for epoch in range(num_epoch):

        # Training
        for batch_index, (data, target) in enumerate(train_loader):
            optimizer_dropout.zero_grad()
            output = model_dropout(data)
            loss = criterion2(output, target)
            loss.backward()
            optimizer_dropout.step()
        training2_dropout_loss.append([epoch, round(loss.item(), 3)])
        training2_dropout_epoch_loss.append(round(loss.item(), 3))


    torch.save(model_dropout, "crt2_model_dropout.pt")
    model_dropout = torch.load("crt2_model_dropout.pt")
    loss_dlist = []


    
    avg_list =[]
    std_list =[]
    model_dropout.eval()
    model_dropout.apply(apply_dropout)

    with torch.no_grad():
        isr =IS()
        x_list=[]
        y_list = []
        
        for batch_index, (data, target) in enumerate(validation_loader):
            tmp_list = []
            for idx in range(100):
                output_dropout = model_dropout(data)
                tmp_list.append(output_dropout)
            avg = np.average(tmp_list)
            std = np.std(tmp_list)
            yhat = torch.distributions.Normal(avg,std)
            for idx in range(len(tmp_list)):
                cdf = yhat.cdf(tmp_list[idx])
                x_list.append(cdf)
            avg_list.append(avg)
            std_list.append(std)
            loss_dropout = criterion2(avg, target)
            loss_dlist.append(loss_dropout.item())
        for i in range(len(x_list)):
                cdf = x_list[i]
                cnt = 0
                for j in range(len(x_list)):
                    if(x_list[j]<=cdf):
                        cnt+=1
                y_list.append(cnt/len(x_list))
        err_before = getErr(y_list)
        #isotonic regression here
        isr.fit_transform(x_list,y_list)
        yhat_mod = isr.predict(x_list)
        err_after = getErr(yhat_mod)
        #error calculation
        #Assume that the confidence levels will be 0.1, 0.2 ,0.3, 0.4,....

    loss_dropout_avg = np.average(loss_dlist)
    f = open("output.txt", "w")
    f.write("\nTraining Loss with criterion 2 with dropout: \n")
    f.write(" ".join(training2_dropout_loss.__str__()))
    f.write("\nAverage loss of model trained with criterion 2 with dropout\n")
    f.write(str(loss_dropout_avg))
    f.write("\nWithin First Stdv \n")
    f.write(" ".join(p1_list.__str__()))
    f.write("\nWithin second Stdv \n")
    f.write(" ".join(p2_list.__str__()))

    f.write("\n Avg_list: \n")
    f.write(" ".join(avg_list.__str__()))

    f.write("\n std_list: \n")
    f.write(" ".join(std_list.__str__()))
    f.close()


    #SUMMARY WRITER
    writer = SummaryWriter("./logs")
    for idx in range(len(avg_list)):
        writer.add_scalars(
            "Mean and stdv of prediction",
            {"Mean:": avg_list[idx], "Standard Deviation": std_list[idx]},
            idx
        )
    writer.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--xpath", type=str, default="x.npy", help="path to x file")
    parser.add_argument("--ypath", type=str, default="y.npy", help="path to y file")

    args = parser.parse_args()

    main(args.xpath, args.ypath)